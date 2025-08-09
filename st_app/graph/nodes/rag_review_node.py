import os
from typing import Dict

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda

from st_app.rag.embedder import build_or_load_faiss
from st_app.rag.prompt import RAG_REVIEW_PROMPT
from st_app.rag.llm import get_llm
from st_app.rag.retriever import retrieve_reviews
from st_app.utils.state import GraphState


INDEX_DIR = os.path.join("st_app", "db", "faiss_index")
_STORE, _EMBED = build_or_load_faiss(INDEX_DIR)


def rag_review_node() -> RunnableLambda:
    prompt = ChatPromptTemplate.from_messages([
        ("system", RAG_REVIEW_PROMPT),
        ("human", "사용자 질문: {user_input}\n\n리뷰 컨텍스트:\n{context}"),
    ])
    llm = get_llm()
    chain = prompt | llm

    def _invoke(state: GraphState) -> GraphState:
        query = state.get("user_input", "")
        context, citations = retrieve_reviews(_STORE, query)
        response = chain.invoke({"user_input": query, "context": context})
        text = response.content if hasattr(response, "content") else str(response)
        state["response"] = text
        state["citations"] = citations
        state["route"] = "rag_review"
        state["last_node"] = "rag_review"
        return state

    return RunnableLambda(_invoke)

