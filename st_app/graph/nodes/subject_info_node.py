import json
import os
from typing import Dict

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda

from st_app.rag.llm import get_llm
from st_app.rag.prompt import SUBJECT_INFO_PROMPT
from st_app.utils.state import GraphState


SUBJECT_DB_PATH = os.path.join("st_app", "db", "subject_information", "subjects.json")


def _load_subjects() -> Dict[str, Dict]:
    if not os.path.exists(SUBJECT_DB_PATH):
        return {}
    with open(SUBJECT_DB_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def subject_info_node() -> RunnableLambda:
    prompt = ChatPromptTemplate.from_messages([
        ("system", SUBJECT_INFO_PROMPT),
        ("human", "대상: {subject}\n기본 정보: {info}\n\n사용자 질문: {user_input}"),
    ])
    llm = get_llm()
    chain = prompt | llm

    subjects = _load_subjects()

    def _invoke(state: GraphState) -> GraphState:
        subject = state.get("subject")
        if subject and subject in subjects:
            enrich = subjects[subject]
        else:
            enrich = {}
        response = chain.invoke({
            "subject": subject or "(미상)",
            "user_input": state.get("user_input", ""),
            "info": enrich,
        })
        text = response.content if hasattr(response, "content") else str(response)
        state["response"] = text
        state["route"] = "subject_info"
        state["last_node"] = "subject_info"
        return state

    return RunnableLambda(_invoke)

