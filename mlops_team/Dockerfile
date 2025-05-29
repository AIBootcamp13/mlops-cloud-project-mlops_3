FROM python:3.9-slim

WORKDIR /app

# COPY requirements.txt .
COPY requirements.txt /app/requirements.txt
# RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt


# 도커 이미지 빌드 할 때 모든 파일, 하위 폴더를 복사(민감한 정보 유출 가능성 있으니 주의)
# TODO: 나중에 수정 고려하기
# COPY . .
COPY . /app/


# fastapi 기본 포트
EXPOSE 8000


CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]