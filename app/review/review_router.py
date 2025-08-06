import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from fastapi import APIRouter, HTTPException
from database.mongodb_connection import mongo_db
from app.responses.base_response import BaseResponse
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any

review = APIRouter(prefix="/review", tags=["Review"])

class ReviewPreprocessService:
    """리뷰 전처리 서비스 (review_router.py 내부 클래스)"""
    
    def preprocess_data(self, raw_data: List[Dict], site_name: str) -> List[Dict]:
        """원본 데이터를 전처리하여 반환"""
        try:
            # 딕셔너리 리스트를 DataFrame으로 변환
            df = pd.DataFrame(raw_data)
            
            # 공통 전처리 적용
            df = self._apply_common_preprocessing(df, site_name)
            
            # DataFrame을 다시 딕셔너리 리스트로 변환
            preprocessed_data = df.to_dict('records')
            
            # 각 레코드에 전처리 메타데이터 추가
            for record in preprocessed_data:
                record['site'] = site_name
                record['preprocessed_at'] = datetime.now()
                record['is_preprocessed'] = True
            
            return preprocessed_data
            
        except Exception as e:
            print(f"전처리 중 오류 발생: {str(e)}")
            return []
    
    def _apply_common_preprocessing(self, df: pd.DataFrame, site_name: str) -> pd.DataFrame:
        """모든 사이트에 공통으로 적용되는 전처리"""
        
        # 1. 결측치 제거
        df = df.dropna()
        
        # 2. 평점 이상치 처리 (1~5점 범위)
        score_columns = ['score', 'rating', 'star', 'stars']
        score_col = None
        for col in score_columns:
            if col in df.columns:
                score_col = col
                break
        
        if score_col:
            df = df[df[score_col].between(1, 5)]
        
        # 3. 리뷰 텍스트 길이 필터링 (5자 이상 200자 이하)
        text_columns = ['text', 'review', 'content', 'comment']
        text_col = None
        for col in text_columns:
            if col in df.columns:
                text_col = col
                break
                
        if text_col:
            df = df[df[text_col].str.len().between(5, 200)]
            # 텍스트 정제 (특수문자 제거)
            df[text_col] = df[text_col].str.replace(r'[^0-9A-Za-z가-힣\s\.\,\!\?]', '', regex=True)
        
        # 4. 날짜 관련 파생변수 생성
        date_columns = ['date', 'created_at', 'review_date']
        date_col = None
        for col in date_columns:
            if col in df.columns:
                date_col = col
                break
                
        if date_col:
            try:
                # 상대적 날짜 표현 처리 (예: "3달 전", "1달 전")
                if df[date_col].astype(str).str.contains('전', na=False).any():
                    print(f"상대적 날짜 표현 감지됨: {site_name}")
                    # 상대적 날짜는 현재 시점으로 대체하거나 스킵
                    df['has_relative_date'] = True
                else:
                    # 절대적 날짜 표현 처리
                    df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
                    # NaT 값이 있는 행들을 제거
                    valid_date_mask = df[date_col].notna()
                    df = df[valid_date_mask]
                    
                    if len(df) > 0:  # 유효한 날짜가 있는 경우에만 파생변수 생성
                        df['year'] = df[date_col].dt.year
                        df['month'] = df[date_col].dt.month
                        df['weekday'] = df[date_col].dt.weekday
                        df['is_weekend'] = df[date_col].dt.weekday.isin([5, 6])
            except Exception as e:
                print(f"날짜 처리 중 오류: {str(e)}")
                # 날짜 처리 실패 시에도 다른 전처리는 계속 진행
                pass
        
        return df

@review.post("/upload/{site_name}")
async def upload_csv_to_mongodb(site_name: str):
    """
    CSV 파일을 MongoDB에 업로드
    
    Args:
        site_name: 사이트 명 (diningcode, googlemap, kakaomap)
    
    Returns:
        업로드 결과 메시지
    """
    
    # 지원하는 사이트 체크
    supported_sites = ["diningcode", "googlemap", "kakaomap"]
    if site_name not in supported_sites:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 사이트입니다. 지원 사이트: {supported_sites}"
        )
    
    try:
        # CSV 파일 경로 매핑
        csv_files = {
            "diningcode": "database/reviews_diningcode.csv",
            "googlemap": "database/reviews_googlemaps.csv",
            "kakaomap": "database/reviews_kakaomap.csv"
        }
        
        file_path = csv_files[site_name]
        
        # 파일 존재 확인
        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=404,
                detail=f"CSV 파일을 찾을 수 없습니다: {file_path}"
            )
        
        # CSV 파일 읽기
        df = pd.read_csv(file_path)
        
        # MongoDB 컬렉션
        collection = mongo_db["raw_reviews"]
        
        # 기존 데이터 삭제 (같은 사이트)
        delete_result = collection.delete_many({"site": site_name})
        
        # 데이터 준비
        documents = []
        for _, row in df.iterrows():
            doc = row.to_dict()
            doc['site'] = site_name
            doc['uploaded_at'] = datetime.now()
            documents.append(doc)
        
        # MongoDB에 삽입
        if documents:
            insert_result = collection.insert_many(documents)
            
            return BaseResponse(
                message=f"{site_name} 사이트의 {len(documents)}개 리뷰가 성공적으로 업로드되었습니다.",
                data={
                    "site": site_name,
                    "uploaded_count": len(documents),
                    "deleted_count": delete_result.deleted_count,
                    "file_path": file_path
                }
            )
        else:
            raise HTTPException(
                status_code=400,
                detail="업로드할 데이터가 없습니다."
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"업로드 중 오류 발생: {str(e)}"
        )

@review.post("/preprocess/{site_name}")
async def preprocess_reviews(site_name: str):
    """
    특정 사이트의 크롤링 데이터를 MongoDB에서 조회하여 전처리 후 저장
    
    Args:
        site_name: 사이트 명 (diningcode, googlemap, kakaomap)
    
    Returns:
        전처리 결과 메시지
    """
    
    # 지원하는 사이트 체크
    supported_sites = ["diningcode", "googlemap", "kakaomap"]
    if site_name not in supported_sites:
        raise HTTPException(
            status_code=400, 
            detail=f"지원하지 않는 사이트입니다. 지원 사이트: {supported_sites}"
        )
    
    try:
        # MongoDB 컬렉션 정의
        raw_reviews_collection = mongo_db["raw_reviews"]
        preprocessed_reviews_collection = mongo_db["preprocessed_reviews"]
        
        # 전처리 서비스 생성
        preprocess_service = ReviewPreprocessService()
        
        # 원본 데이터 조회
        raw_data = list(raw_reviews_collection.find({"site": site_name}))
        
        if not raw_data:
            raise HTTPException(
                status_code=404,
                detail=f"{site_name} 사이트의 원본 데이터가 없습니다. 먼저 /upload/{site_name} API를 사용해서 데이터를 업로드해주세요."
            )
        
        # 전처리 실행
        preprocessed_data = preprocess_service.preprocess_data(raw_data, site_name)
        
        # 전처리된 데이터 저장
        if preprocessed_data:
            # 기존 전처리 데이터 삭제
            delete_result = preprocessed_reviews_collection.delete_many({"site": site_name})
            
            # 새로운 전처리 데이터 삽입
            insert_result = preprocessed_reviews_collection.insert_many(preprocessed_data)
            
            return BaseResponse(
                message=f"{site_name} 사이트의 {len(preprocessed_data)}개 리뷰가 성공적으로 전처리되었습니다.",
                data={
                    "site": site_name,
                    "processed_count": len(preprocessed_data),
                    "original_count": len(raw_data),
                    "deleted_previous": delete_result.deleted_count
                }
            )
        else:
            raise HTTPException(
                status_code=500,
                detail="전처리 과정에서 오류가 발생했습니다."
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"전처리 중 오류 발생: {str(e)}"
        )

@review.get("/status")
async def get_mongodb_status():
    """
    MongoDB 상태 및 데이터 현황 확인
    
    Returns:
        MongoDB 연결 상태 및 데이터 통계
    """
    
    try:
        # MongoDB 연결 테스트
        mongo_db.command('ping')
        
        # 컬렉션별 데이터 수 확인
        raw_collection = mongo_db["raw_reviews"]
        preprocessed_collection = mongo_db["preprocessed_reviews"]
        
        status_data = {
            "connection": "OK",
            "raw_reviews": {},
            "preprocessed_reviews": {}
        }
        
        # 사이트별 원본 데이터 수
        for site in ["diningcode", "googlemap", "kakaomap"]:
            raw_count = raw_collection.count_documents({"site": site})
            preprocessed_count = preprocessed_collection.count_documents({"site": site})
            
            status_data["raw_reviews"][site] = raw_count
            status_data["preprocessed_reviews"][site] = preprocessed_count
        
        # 전체 통계
        status_data["total_raw"] = raw_collection.count_documents({})
        status_data["total_preprocessed"] = preprocessed_collection.count_documents({})
        
        return BaseResponse(
            message="MongoDB 상태가 정상입니다.",
            data=status_data
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"MongoDB 상태 확인 중 오류 발생: {str(e)}"
        )