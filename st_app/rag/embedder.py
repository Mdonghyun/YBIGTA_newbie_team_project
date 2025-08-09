from __future__ import annotations

import os
import glob
import pandas as pd
import requests
import json
import numpy as np
from typing import List, Tuple, Optional
from dotenv import load_dotenv

from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.docstore.document import Document
from langchain_community.docstore import InMemoryDocstore
import faiss # faiss-cpu 라이브러리 직접 사용

# 이 함수는 FAISS.load_local 또는 쿼리 임베딩 시 필요하므로 유지합니다.
def get_embedding_model() -> OpenAIEmbeddings:
    load_dotenv()
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
        or "solar-embedding-1-large-passage"
    )

    return OpenAIEmbeddings(
        api_key=api_key,
        base_url=base_url,
        model=embed_model,
    )

def build_or_load_faiss(index_dir: str) -> Tuple[Optional[FAISS], Optional[OpenAIEmbeddings]]:
    try:
        embeddings = get_embedding_model()
    except RuntimeError as e:
        print(e)
        return None, None

    if os.path.exists(os.path.join(index_dir, "index.faiss")):
        try:
            # allow_dangerous_deserialization=True 옵션이 필요합니다.
            store = FAISS.load_local(index_dir, embeddings, allow_dangerous_deserialization=True)
            return store, embeddings
        except Exception as e:
            print(f"Could not load FAISS index: {e}")
            return None, None
    return None, None

def create_documents_from_csvs(csv_paths: list[str]) -> list[Document]:
    documents = []
    column_map = {
        "diningcode": "text",
        "googlemap": "content",
        "kakaomap": "review"
    }

    for csv_path in csv_paths:
        review_column = None
        file_name = os.path.basename(csv_path)
        
        for name, col in column_map.items():
            if name in file_name:
                review_column = col
                break
        
        if not review_column:
            print(f"Warning: Skipping {file_name} as it does not match known sources.")
            continue

        try:
            df = pd.read_csv(csv_path)
            print(f"Processing {file_name}, using column: '{review_column}'")
        except Exception as e:
            print(f"Warning: Could not read {csv_path}. Error: {e}")
            continue

        for index, row in df.iterrows():
            review_text = row.get(review_column)
            if pd.isna(review_text):
                continue
            cleaned_text = str(review_text).strip()
            if not cleaned_text:
                continue

            metadata = {
                "source": file_name,
                "row_index": index,
                "rating": row.get("rating", 0.0),
                "date": row.get("date", "N/A"),
                "user": row.get("user", "N/A"),
            }
            if 'id' in row and pd.notna(row['id']):
                metadata['id'] = row['id']

            documents.append(Document(page_content=cleaned_text, metadata=metadata))
    return documents

def get_embedding_vector_direct(text: str, api_key: str) -> List[float]:
    """
    requests를 사용해 Upstage API에서 직접 임베딩 벡터를 가져옵니다.
    """
    response = requests.post(
        "https://api.upstage.ai/v1/embeddings",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={"input": text, "model": "solar-embedding-1-large-passage"}
    )
    response.raise_for_status()
    return response.json()["data"][0]["embedding"]

def build_index():
    """
    LangChain을 우회하여 직접 API를 호출하고 FAISS 인덱스를 생성합니다.
    """
    print("API 키를 환경변수에서 로드합니다...")
    load_dotenv()
    api_key = os.getenv("UPSTAGE_API_KEY")
    if not api_key:
        print("UPSTAGE_API_KEY가 설정되지 않았습니다.")
        return

    script_dir = os.path.dirname(__file__)
    csv_dir = os.path.abspath(os.path.join(script_dir, "..", "..", "database"))
    csv_paths = glob.glob(os.path.join(csv_dir, "preprocessed_reviews_*.csv"))
    
    if not csv_paths:
        print(f"'{csv_dir}'에서 CSV 파일을 찾을 수 없습니다.")
        return

    documents = create_documents_from_csvs(csv_paths)
    if not documents:
        print("처리할 문서가 없습니다.")
        return

    print(f"총 {len(documents)}개의 문서를 임베딩합니다. 시간이 다소 걸릴 수 있습니다...")
    
    embeddings_list = []
    for i, doc in enumerate(documents):
        try:
            vector = get_embedding_vector_direct(doc.page_content, api_key)
            embeddings_list.append(vector)
            if (i + 1) % 100 == 0:
                print(f"... {i+1}/{len(documents)}개 문서 임베딩 완료 ...")
        except Exception as e:
            print(f"문서 {i} (출처: {doc.metadata.get('source')}) 임베딩 중 오류 발생: {e}")
            return

    print("모든 문서의 임베딩을 완료했습니다. FAISS 인덱스를 구성합니다...")

    embedding_dim = len(embeddings_list[0])
    index = faiss.IndexFlatL2(embedding_dim)
    
    docstore = InMemoryDocstore({str(i): doc for i, doc in enumerate(documents)})
    index_to_docstore_id = {i: str(i) for i in range(len(documents))}
    
    embeddings_array = np.array(embeddings_list, dtype="float32")
    index.add(embeddings_array)

    # LangChain FAISS 객체로 최종 조립. 쿼리 임베딩을 위해 embed_query 함수를 전달합니다.
    # solar-embedding-1-large-query 모델을 사용하도록 새 임베딩 객체를 만듭니다.
    query_embedder = OpenAIEmbeddings(
        api_key=api_key,
        base_url="https://api.upstage.ai/v1",
        model="solar-embedding-1-large-query"
    )

    final_faiss_store = FAISS(query_embedder.embed_query, index, docstore, index_to_docstore_id)

    index_dir = os.path.abspath(os.path.join(script_dir, "..", "db", "faiss_index"))
    os.makedirs(index_dir, exist_ok=True)
    print(f"FAISS 인덱스를 '{index_dir}'에 저장합니다...")
    final_faiss_store.save_local(index_dir)
    
    print("FAISS 인덱스 생성이 완료되었습니다.")

if __name__ == "__main__":
    build_index()

