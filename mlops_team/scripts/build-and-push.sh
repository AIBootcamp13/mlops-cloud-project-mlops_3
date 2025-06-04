#!/bin/bash

# 1. .env에서 환경변수 불러오기
set -o allexport
source ../.env || { echo "❌ .env 파일을 찾을 수 없습니다."; exit 1; }
set +o allexport

# 2. Docker 이미지 빌드
echo "Building Docker image ..."
docker build -t $DOCKERHUB_USERNAME/weather-api:latest . || { echo "❌ Docker 이미지 빌드 실패"; exit 1; }

# 3. Docker Hub 로그인
echo "Trying to log in to Docker Hub..."
echo $DOCKERHUB_TOKEN | docker login -u $DOCKERHUB_USERNAME --password-stdin || { echo "❌ Docker Hub 로그인 실패"; exit 1; }

# 4. 이미지 푸시
echo "Pushing to Docker Hub..."
docker push $DOCKERHUB_USERNAME/weather-api:latest || { echo "❌ 이미지 푸시 실패"; exit 1; }

# 모든 단계 성공 시
echo "✅ Docker 이미지 빌드 및 푸시 완료!"