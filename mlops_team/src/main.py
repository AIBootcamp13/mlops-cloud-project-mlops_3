from fastapi import FastAPI
from .model import predict_temperature_after_1_hour
import pandas as pd

from .clothing_rules import get_cloth_sense

app = FastAPI(title="Temperature Prediction API", version="0.1.0")

''' < API의 활용 흐름 >

사용자 요청 (현재 날씨 정보) → API 서버 (src/main.py)
API 서버 (src/main.py) → 모델 로직 (src/model.py)에 예측 요청 (현재 날씨 정보 전달)
모델 로직 (src/model.py) → 저장된 LinearRegression 모델 (*.pkl 파일)을 사용해 1시간 뒤 기온 예측
모델 로직 (src/model.py) → API 서버 (src/main.py)에 예측 결과 전달
API 서버 (src/main.py) → 예측 결과 + 옷차림 추천 규칙 적용 → 사용자에게 최종 응답 (JSON)
'''


# 서버 잘 열렸는지 확인용
@app.get("/")
async def read_root():
    return {"message": "Welcome to the Temperature Prediction API"}

@app.get("/predict-future-temp")
async def get_future_temp_prediction(
    current_temp: float,
    current_humidity: float,
    current_windspeed: float,
    current_hour: int,
    location: str = 'Busan'
):
    
    predicted_temp = predict_temperature_after_1_hour(
        current_temp, current_humidity, current_windspeed, current_hour
    )

    if predicted_temp == None:
        return  {"error": "failed to predict temperature. Please check the input values."}
    

    recommendation = get_cloth_sense(predicted_temp)
    return {
        "location": location,
        "current_weather_input": {
            "temperature": current_temp,
            "humidity": current_humidity,
            "windspeed": current_windspeed,
            "hour": current_hour
        },
        "predicted_1hr_future_temperature": round(predicted_temp, 2),
        "clothing_recommendation": recommendation # 다음 스텝에서 추가
    }
    