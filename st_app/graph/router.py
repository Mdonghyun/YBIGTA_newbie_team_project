from __future__ import annotations

import os
import json
import re
from typing import Literal, List

from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.prompts import ChatPromptTemplate

from st_app.rag.llm import get_llm
from st_app.rag.prompt import ROUTER_SYSTEM_PROMPT
from st_app.utils.state import GraphState
from st_app.graph.nodes.chat_node import chat_node
from st_app.graph.nodes.subject_info_node import subject_info_node
from st_app.graph.nodes.rag_review_node import rag_review_node


def _router_decision_fn(state: GraphState) -> Literal["chat", "subject_info", "rag_review"]:
    prompt = ChatPromptTemplate.from_messages([
        ("system", ROUTER_SYSTEM_PROMPT),  # ← prompt.py에서 JSON 한 줄로 강제된 버전 사용
        ("human",
         "가능한 subject 후보: {candidates}\n"
         "대화 이력: {history}\n\n"
         "사용자 입력: {user_input}\n"
         "JSON 한 줄로만 답하세요.")
    ])
    llm = get_llm(temperature=0.0)
    chain = prompt | llm

    candidates_list: List[str] = _load_candidate_subjects()
    response = chain.invoke({
        "history": [(m["role"], m["content"]) for m in state.get("history", []) if m.get("content")],
        "user_input": state.get("user_input", ""),
        "candidates": ", ".join(candidates_list) if candidates_list else "(없음)",
    })
    text = response.content if hasattr(response, "content") else str(response)

    # JSON 안전 파싱
    route = "chat"
    subject = None
    try:
        data = json.loads(text.strip())
        route = data.get("route", "chat")
        subject = data.get("subject")
        if isinstance(subject, str):
            subject = subject.strip() or None
    except Exception:
        # 혹시 모델이 JSON을 깨뜨리면 기존 정규식으로 백업
        m = re.search(r'"route"\s*:\s*"([a-z_]+)"', text)
        if m:
            route = m.group(1)
        m2 = re.search(r'"subject"\s*:\s*"([^"]+)"', text)
        if m2:
            subject = m2.group(1).strip()

    # 라우트/서브젝트 보정
    if route not in {"chat", "subject_info", "rag_review"}:
        route = "chat"

    if not subject:
        guessed = _guess_subject(state.get("user_input", ""), candidates_list)
        subject = guessed or state.get("subject") or None

    if route in {"subject_info", "rag_review"} and not subject and len(candidates_list) == 1:
        subject = candidates_list[0]

    state["subject"] = subject
    return route  # type: ignore[return-value]



SUBJECT_DB_PATH = os.path.join("st_app", "db", "subject_information", "subjects.json")

def _guess_subject(user_input: str, candidates: List[str]) -> str | None:
    ui = (user_input or "").lower()
    aliases = {
        "명동교자": "명동교자 본점",
        "교자": "명동교자 본점",
    }
    for k, v in aliases.items():
        if k in ui and v in candidates:
            return v
    for c in candidates:
        if c.lower() in ui or c.replace(" ", "").lower() in ui:
            return c
    if len(candidates) == 1:
        return candidates[0]
    return None


def _load_candidate_subjects() -> List[str]:
    if not os.path.exists(SUBJECT_DB_PATH):
        return []
    try:
        with open(SUBJECT_DB_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return list(data.keys())
    except Exception:
        return []
    return []


def build_graph():
    workflow = StateGraph(GraphState)

    # 노드 정의
    workflow.add_node("chat", chat_node())
    workflow.add_node("subject_info", subject_info_node())
    workflow.add_node("rag_review", rag_review_node())

    # 라우터 가상 노드: 상태 그대로 통과시키는 더미 구현
    def router_node(state: GraphState) -> GraphState:
        if not state.get("subject"):
            cands = _load_candidate_subjects()
            if len(cands) == 1:
                state["subject"] = cands[0]
        return state


    workflow.add_node("router", router_node)

    # router 에서 LLM 라우팅으로 분기
    def _route_selector(state: GraphState):
        return _router_decision_fn(state)

    workflow.add_conditional_edges(
        "router",
        _route_selector,
        {
            "chat": "chat",
            "subject_info": "subject_info",
            "rag_review": "rag_review",
        },
    )

    # 처리 후 Chat 으로 복귀, 그 다음 종료
    workflow.add_edge("subject_info", "chat")
    workflow.add_edge("rag_review", "chat")
    workflow.add_edge("chat", END)

    workflow.set_entry_point("router")

    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)
    return app

