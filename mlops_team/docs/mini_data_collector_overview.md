#  mini_data_collector.py 코드 흐름

1. 현재 시간의 날씨 실황 데이터를 기상청 API에서 받아오고  
2. 그와 짝을 이루는 1시간 뒤 예보 기온도 받아서  
3. 현재 → 미래로 이어지는 한 쌍의 학습 데이터를 만든 뒤  
4. CSV 파일에 저장해서 머신러닝 학습에 쓸 수 있게 쌓아두는 스크립트  

테스트 용으로 3시간 동안 1시간 간격으로 3번 실행(지금은 5초로 단축)해서 데이터 몇 줄이라도 모으자!

---

# API의 활용 흐름

1. 사용자 요청 (현재 날씨 정보) → API 서버 (src/main.py)  
2. API 서버 (src/main.py) → 모델 로직 (src/model.py)에 예측 요청 (현재 날씨 정보 전달)  
3. 모델 로직 (src/model.py) → 저장된 LinearRegression 모델 (*.pkl 파일)을 사용해 1시간 뒤 기온 예측  
4. 모델 로직 (src/model.py) → API 서버 (src/main.py)에 예측 결과 전달  
5. API 서버 (src/main.py) → 예측 결과 + 옷차림 추천 규칙 적용 → 사용자에게 최종 응답 (JSON)

---

#  구현한 컴포넌트 총정리 (초간단 버전)

1. Source code / source repository (GitHub)  
2. Automated data pipeline (기상청 API를 호출해서 데이터 수집)  
3. Model registry (pickle)  
4. CD (fast API, prediction service)

---

# 앞으로 시도해볼만한 컴포넌트

1. CI (코드 품질 검사, 테스트 자동화)  
2. Data anaytics (수집된 데이터 분석)  
3. GitHub Actions (자동화된 배포 파이프라인)  
4. Model monitoring (모델 성능 모니터링)  
5. Airflow (데이터 파이프라인)  
6. Jira (프로젝트 관리)
