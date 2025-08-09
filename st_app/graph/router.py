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
        ("system", ROUTER_SYSTEM_PROMPT),
        (
            "human",
            "가능한 subject 후보: {candidates}\n대화 이력: {history}\n\n사용자 입력: {user_input}\n"
            "반드시 한 줄로만 답하세요. 예) route=subject_info; subject=명동교자",
        ),
    ])
    llm = get_llm(temperature=0.0)
    chain = prompt | llm
    # subject 후보 로딩
    candidates_list: List[str] = _load_candidate_subjects()
    response = chain.invoke({
        "history": [(m["role"], m["content"]) for m in state.get("history", []) if m.get("content")],
        "user_input": state.get("user_input", ""),
        "candidates": ", ".join(candidates_list) if candidates_list else "(없음)",
    })
    text = response.content if hasattr(response, "content") else str(response)
    # 포맷: route=xxx; subject=yyy  (LLM 판단만 사용)
    route = "chat"
    subject = None
    m = re.search(r"route\s*=\s*([a-z_]+)", text)
    if m:
        route = m.group(1)
    m2 = re.search(r"subject\s*=\s*(.+)$", text)
    if m2:
        subj_raw = m2.group(1).strip()
        if subj_raw.lower() == "null":
            subject = None
        else:
            subject = subj_raw
    state["subject"] = subject
    if route not in {"chat", "subject_info", "rag_review"}:
        route = "chat"
    return route  # type: ignore[return-value]


SUBJECT_DB_PATH = os.path.join("st_app", "db", "subject_information", "subjects.json")


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
    def router_node(state: GraphState) -> GraphState:  # noqa: D401
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

