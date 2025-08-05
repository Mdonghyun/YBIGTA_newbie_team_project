# 1. 베이스 이미지 설정
FROM python:3.11

# 2. 컨테이너 내 작업 디렉토리 설정
WORKDIR /app

# 3. requirements.txt 복사 후 패키지 설치
COPY requirements_cleaned.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 4. 전체 프로젝트 복사
COPY . .

# 5. FastAPI 서버 실행
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]