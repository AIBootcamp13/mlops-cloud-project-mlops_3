import pickle
import pandas as pd

MODEL_PATH = "src/temperature_model.pkl"
model = None

with open(MODEL_PATH, "rb") as f:
    model = pickle.load(f)
print("Model loaded successfully.")

def predict_temperature_after_1_hour(current_temp: float, 
                                     current_humidity: float,
                                     current_windspeed: float, 
                                     current_hour: int) -> float:
    if model is None:
        print("Model is not loaded.")
        return None
    
    input_data = pd.DataFrame({
        '현재기온': [current_temp],
        '현재습도': [current_humidity],
        '현재풍속': [current_windspeed],
        '시각': [current_hour]
    })

    prediction = model.predict(input_data)
    return prediction[0]
