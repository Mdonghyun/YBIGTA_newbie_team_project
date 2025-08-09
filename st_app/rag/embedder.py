from __future__ import annotations

import os
from typing import List, Tuple, Optional

import numpy as np
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS


def build_or_load_faiss(index_dir: str) -> Tuple[Optional[FAISS], Optional[OpenAIEmbeddings]]:
    """
    인덱스 디렉터리에 FAISS 인덱스가 존재하면 로드, 없으면 빈 인덱스를 생성합니다.
    임베딩 모델은 OpenAI 호환 임베딩을 사용합니다.
    """
    # Upstage 우선 사용 (OpenAI 호환 엔드포인트)
    upstage_key = os.getenv("UPSTAGE_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    api_key = upstage_key or openai_key
    if not api_key:
        raise RuntimeError("UPSTAGE_API_KEY 또는 OPENAI_API_KEY 중 하나는 반드시 설정해야 합니다.")

    base_url = os.getenv("UPSTAGE_BASE_URL") or os.getenv("OPENAI_BASE_URL")
    if (not base_url) and upstage_key:
        base_url = "https://api.upstage.ai/v1"

    embed_model = (
        os.getenv("UPSTAGE_EMBEDDING_MODEL")
        or os.getenv("OPENAI_EMBEDDING_MODEL")
        or "text-embedding-3-small"
    )

    embeddings = OpenAIEmbeddings(
        api_key=api_key,
        base_url=base_url,
        model=embed_model,
    )

    if os.path.exists(os.path.join(index_dir, "index.faiss")) and os.path.exists(
        os.path.join(index_dir, "meta.json")
    ):
        try:
            store = FAISS.load_local(index_dir, embeddings, allow_dangerous_deserialization=True)
            return store, embeddings
        except Exception:
            # 손상되었거나 플레이스홀더일 수 있음 → None 반환하여 검색 시 graceful degrade
            return None, None

    # 인덱스가 없으면 생성하지 않고 None 반환 (앱 시작 시 임베딩 호출을 피함)
    return None, None

