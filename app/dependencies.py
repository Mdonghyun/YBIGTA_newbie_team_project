import os
import builtins
from fastapi import Depends
from sqlalchemy.orm import Session
from dotenv import load_dotenv

# 먼저 .env 파일 로드
load_dotenv()

# mysql_connection.py에서 필요한 전역 변수들을 builtins에 설정
# .env 파일의 MYSQL_* 변수들을 mysql_connection.py가 기대하는 이름으로 매핑
builtins.user = os.getenv('MYSQL_USER', 'root')
builtins.passwd = os.getenv('MYSQL_PASSWORD', '')
builtins.host = os.getenv('MYSQL_HOST', 'localhost')
builtins.port = os.getenv('MYSQL_PORT', '3306')
builtins.db = os.getenv('MYSQL_DATABASE', 'ybigta_project')

# 이제 mysql_connection을 import (전역 변수 설정 후)
from database.mysql_connection import SessionLocal, engine

# UserRepository import (mysql_connection 이후)
from app.user.user_repository import UserRepository, Base
from app.user.user_service import UserService

# 테이블 생성
Base.metadata.create_all(bind=engine)

def get_db_session() -> Session:
    """데이터베이스 세션 의존성"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_user_repository(db: Session = Depends(get_db_session)) -> UserRepository:
    return UserRepository(db)

def get_user_service(repo: UserRepository = Depends(get_user_repository)) -> UserService:
    return UserService(repo)
