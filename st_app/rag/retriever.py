from __future__ import annotations

from typing import Dict, List, Tuple, Optional

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document


def retrieve_reviews(store: Optional[FAISS], query: str, k: int = 4) -> Tuple[str, List[Dict]]:
    """
    주어진 쿼리에 대해 FAISS 에서 유사 문서를 회수합니다.
    반환: (컨텍스트 텍스트(병합), 인용 메타데이터 리스트)
    """
    if (store is None) or (not query.strip()):
        return "", []
    results: List[Tuple[Document, float]] = store.similarity_search_with_score(query, k=k)
    snippets: List[str] = []
    citations: List[Dict] = []
    for doc, score in results:
        snippet = doc.page_content.strip()
        meta = doc.metadata or {}
        if str(meta.get("id", "")) == "dummy":
            continue
        citations.append({
            "id": str(meta.get("id", "")),
            "source": str(meta.get("source", "")),
            "score": float(score),
            "snippet": snippet[:300],
        })
        snippets.append(snippet)
    context_text = "\n\n".join(snippets)
    return context_text, citations

