import pickle
import pandas as pd
import os

# 기존 코드
# MODEL_PATH = "src/temperature_model.pkl"
# model = None
# 
# with open(MODEL_PATH, "rb") as f:
#     model = pickle.load(f)
# print("Model loaded successfully.")
# 
# def predict_temperature_after_1_hour(current_temp: float, 
#                                      current_humidity: float,
#                                      current_windspeed: float, 
#                                      current_hour: int) -> float:
#     if model is None:
#         print("Model is not loaded.")
#         return None
#     
#     input_data = pd.DataFrame({
#         '현재기온': [current_temp],
#         '현재습도': [current_humidity],
#         '현재풍속': [current_windspeed],
#         '시각': [current_hour]
#     })
#     prediction = model.predict(input_data)
#     return prediction[0]


# 수정 코드
def load_model(model_dir: str, model_name: str) -> object:
    """
    실험 디렉토리와 모델 파일명을 받아 모델을 동적으로 불러옴
    model_dir: 예) models/experiments/
    model_name: 예) LightGBM_model.pkl
    """
    model_path = os.path.join(model_dir, model_name)
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"모델 파일이 존재하지 않습니다: {model_path}")
    with open(model_path, "rb") as f:
        model = pickle.load(f)
    print(f"Model loaded successfully from {model_path}")
    return model

def predict_temperature_after_1_hour(model, current_temp: float, current_humidity: float, current_windspeed: float, current_hour: int) -> float:
    """
    주어진 모델로 1시간 뒤 온도를 예측합니다.
    """
    input_data = pd.DataFrame({
        '현재기온': [current_temp],
        '현재습도': [current_humidity],
        '현재풍속': [current_windspeed],
        '시각': [current_hour]})
    
    prediction = model.predict(input_data)
    return prediction[0]
