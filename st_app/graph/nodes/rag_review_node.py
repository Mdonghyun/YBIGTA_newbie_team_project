import os
from typing import Dict

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda

from st_app.rag.prompt import RAG_REVIEW_PROMPT
from st_app.rag.llm import get_llm
from st_app.rag.retriever import _load_store, retrieve_reviews
from st_app.utils.state import GraphState

INDEX_DIR = os.path.join("st_app", "db", "faiss_index")
_STORE = _load_store(INDEX_DIR)   # ← 여기서 로드 (Upstage 미니 임베더 사용)

def rag_review_node() -> RunnableLambda:
    prompt = ChatPromptTemplate.from_messages([
        ("system", RAG_REVIEW_PROMPT),
        ("human", "사용자 질문: {user_input}\n\n리뷰 컨텍스트:\n{context}"),
    ])
    llm = get_llm(temperature=0.2)  # 살짝 낮게
    chain = prompt | llm

    def _invoke(state: GraphState) -> GraphState:
        query = state.get("user_input", "").strip()

        # 인덱스/질문 가드
        if not query:
            state["response"] = "질문이 비어 있어요. 어떤 점이 궁금한지 말씀해 주세요!"
            state["citations"] = []
            state["route"] = "rag_review"
            state["last_node"] = "rag_review"
            return state

        if _STORE is None:
            state["response"] = "지금은 리뷰 인덱스를 불러오지 못했어요. 인덱스를 먼저 생성한 뒤 다시 시도해 주세요."
            state["citations"] = []
            state["route"] = "rag_review"
            state["last_node"] = "rag_review"
            return state

        # 검색
        context, citations = retrieve_reviews(_STORE, query, k=5)

        # 근거 없을 때도 부드럽게 응답
        if not context.strip():
            state["response"] = "회수된 리뷰에서 관련 근거를 찾지 못했어요. 다른 표현으로 다시 물어봐 주실래요?"
            state["citations"] = []
            state["route"] = "rag_review"
            state["last_node"] = "rag_review"
            return state

        # 생성
        response = chain.invoke({"user_input": query, "context": context})
        text = response.content if hasattr(response, "content") else str(response)

        state["response"] = text
        state["citations"] = citations
        state["route"] = "rag_review"
        state["last_node"] = "rag_review"
        return state

    return RunnableLambda(_invoke)
