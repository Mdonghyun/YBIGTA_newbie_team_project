from typing import Optional
from sqlalchemy import Column, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session

from app.user.user_schema import User  # 수정하지 않는 조건

# SQLAlchemy ORM용 Base 클래스 정의
Base = declarative_base()

# DB 테이블 모델 정의
class UserModel(Base):
    __tablename__ = "users"

    email = Column(String(255), primary_key=True, index=True)
    password = Column(String(255), nullable=False)
    username = Column(String(255), nullable=False)


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db
        Base.metadata.create_all(bind=db.get_bind())  # 테이블 생성

    def get_user_by_email(self, email: str) -> Optional[User]:
        user = self.db.query(UserModel).filter(UserModel.email == email).first()
        if user:
            return User(
                email=user.email,
                password=user.password,
                username=user.username
            )
        return None

    def save_user(self, user: User) -> User:
        existing = self.db.query(UserModel).filter(UserModel.email == user.email).first()
        if existing:
            existing.password = user.password
            existing.username = user.username
            self.db.commit()
            self.db.refresh(existing)
            return User(
                email=existing.email,
                password=existing.password,
                username=existing.username
            )
        else:
            new_user = UserModel(**user.model_dump())
            self.db.add(new_user)
            self.db.commit()
            self.db.refresh(new_user)
            return User(
                email=new_user.email,
                password=new_user.password,
                username=new_user.username
            )

    def delete_user(self, user: User) -> User:
        db_user = self.db.query(UserModel).filter(UserModel.email == user.email).first()
        if db_user:
            self.db.delete(db_user)
            self.db.commit()
        return user
