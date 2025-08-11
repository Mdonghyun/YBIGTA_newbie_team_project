from __future__ import annotations
from typing import Dict, List, Tuple, Optional
import os
from dotenv import load_dotenv

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

# embedder.py의 미니 임베더를 import (경로 맞춤)
from st_app.rag.embedder import UpstageEmbeddingsMinimal

def _load_store(index_dir: str = "st_app/db/faiss_index") -> Optional[FAISS]:
    load_dotenv()
    api_key = os.getenv("UPSTAGE_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("UPSTAGE_API_KEY/OPENAI_API_KEY 미설정")
        return None
    base_url = os.getenv("UPSTAGE_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "https://api.upstage.ai/v1"
    emb = UpstageEmbeddingsMinimal(api_key=api_key, base_url=base_url, model_query="solar-embedding-1-large-query")
    try:
        store = FAISS.load_local(index_dir, embeddings=emb, allow_dangerous_deserialization=True)
        return store
    except Exception as e:
        print(f"FAISS 인덱스 로드 실패: {e}")
        return None

def retrieve_reviews(store: Optional[FAISS], query: str, k: int = 4) -> Tuple[str, List[Dict]]:
    if (store is None) or (not query.strip()):
        return "", []
    results: List[Tuple[Document, float]] = store.similarity_search_with_score(query, k=k)
    snippets, citations = [], []
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
    return "\n\n".join(snippets), citations
