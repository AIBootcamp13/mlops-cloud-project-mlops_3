import os
import time
from datetime import datetime, timedelta
import requests
import pandas as pd
from dotenv import load_dotenv

'''
< 코드 흐름 >
1. 현재 시간의 날씨 실황 데이터를 기상청 API에서 받아오고
2. 그와 짝을 이루는 1시간 뒤 예보 기온도 받아서
3. 현재 → 미래로 이어지는 한 쌍의 학습 데이터를 만든 뒤
4. CSV 파일에 저장해서 머신러닝 학습에 쓸 수 있게 쌓아두는 스크립트

테스트 용으로 3시간 동안 1시간 간격으로 3번 실행(지금은 5초로 단축)해서 데이터 몇 줄이라도 모으자! 

< 구현한 컴포넌트 총정리(초간단 버전)>
1. Source code / source repository(GitHub)
2. Automated data pipeline(기상청 API를 호출해서 데이터 수집)
3. Model registry(pickle)
4. CD(fast API, prediction service)

< 앞으로 시도해볼만한 컴포넌트 >
1. CI (코드 품질 검사, 테스트 자동화)
2. Data anaytics (수집된 데이터 분석)
3. git actions (자동화된 배포 파이프라인)
4. Model monitoring (모델 성능 모니터링)
5. airflow (데이터 파이프라인)
6. JIRA (프로젝트 관리)
'''

load_dotenv()  

# 설정값
API_KEY = os.getenv("API_KEY")
NX = "98"  # 부산광역시청 좌표 예시로 사용함
NY = "76"  
CSV_FILE_PATH = './data/collected_weather_data.csv' # 프로젝트 루트의 data 폴더 기준

# API_KEY가 로드되었는지 확인
if not API_KEY:
    print("error: API_KEY가 설정되지 않았습니다.")
else:
    print("API_KEY가 성공적으로 로드되었습니다.") # 확인용 로그

def get_weather_data(base_datetime_param, data_type): # 파라미터 이름을 base_datetime_param으로 변경
            """
            기상청 API에서 초단기실황 또는 초단기예보 데이터를 가져옵니다.
            data_type: "초단기실황" 또는 "초단기예보"
            """
            # 현재 실제 시간을 기준으로 base_date와 base_time을 결정
            now_for_api = datetime.now() # API 호출 시점의 실제 시간

            if data_type == "초단기실황":
                url = "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst"
                # 초단기실황: 가장 최근 발표된 정시 데이터. 보통 현재 시간보다 1시간 전 데이터를 요청하면 안정적.
                # 만약 현재 시각이 17:03 이라면, 16:00 데이터를 요청.
                query_base_datetime = now_for_api - timedelta(hours=1)
                query_base_time = query_base_datetime.strftime("%H00")
                query_base_date = query_base_datetime.strftime("%Y%m%d")

            elif data_type == "초단기예보":
                url = "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtFcst"
                # 초단기예보: 가장 최근 발표 시각 (보통 30분 간격, 예: 00, 30분)
                # API 명세에 따르면 초단기예보는 매시간 30분에 생성되어 40분부터 제공
                # 가장 안정적인 것은 현재 시간 기준으로 가장 최근의 "발표가 완료된" 예보를 가져오는 것
                if now_for_api.minute < 45: # 45분 이전이면, 이전 시간 30분 발표 예보 (더 보수적으로)
                    query_base_datetime = now_for_api - timedelta(hours=1)
                    query_base_time = query_base_datetime.strftime("%H30")
                else: # 45분 이후면, 현재 시간 30분 발표 예보
                    query_base_datetime = now_for_api
                    query_base_time = query_base_datetime.strftime("%H30")
                query_base_date = query_base_datetime.strftime("%Y%m%d")
            else:
                return None

            params = {
                "serviceKey": API_KEY,
                "pageNo": "1",
                "numOfRows": "100",
                "dataType": "JSON",
                "base_date": query_base_date, # 계산된 query_base_date 사용
                "base_time": query_base_time, # 계산된 query_base_time 사용
                "nx": NX,
                "ny": NY,
            }
            try:
                print(f"\nRequesting URL: {url}")
                print(f"Request Data Type: {data_type}")
                print(f"Request Params: {params}")

                response = requests.get(url, params=params, timeout=10)

                print(f"Response Status Code: {response.status_code}")
                print(f"Response Text (first 500 chars): {response.text[:500]}")

                response.raise_for_status()
                data = response.json()

                if data.get("response", {}).get("header", {}).get("resultCode") == "00":
                    return data["response"]["body"]["items"]["item"]
                else:
                    error_code = data.get("response", {}).get("header", {}).get("resultCode")
                    error_msg = data.get("response", {}).get("header", {}).get("resultMsg")
                    print(f"API Error Code: {error_code}, API Error Message: {error_msg}")
                    return None
            except requests.exceptions.JSONDecodeError as e:
                print(f"JSONDecodeError: {e}")
                print("API 응답이 JSON 형식이 아니거나 비어있습니다. 위의 Response Text를 확인해주세요.")
                return None
            except requests.exceptions.RequestException as e:
                print(f"Request Exception: {e}")
                return None
            except Exception as e:
                print(f"An unexpected error occurred: {e}")
                return None

def main():
    collected_data = []
    # 현재 시간 기준으로 base_time 설정 (정시보다 조금 이전 시간으로 하는 것이 안정적일 수 있음)
    # 기상청 API는 보통 정시 발표 후 약 10~15분 뒤에 데이터가 업데이트됨
    # 지금은 단순화를 위해 현재 시간 그대로 사용하고, 필요시 API 명세에 맞춰 base_time 조정
    now = datetime.now()
    base_dt_for_fcst = now - timedelta(minutes=now.minute % 30, seconds=now.second, microseconds=now.microsecond) # 초단기예보는 30분 단위 발표 고려
    if base_dt_for_fcst.minute == 0: # 정시 발표 데이터
         base_dt_for_fcst = base_dt_for_fcst - timedelta(hours=1) # 가장 최근 발표된 정시 데이터 가져오기 위함
         base_dt_for_fcst = base_dt_for_fcst.replace(minute=0) #  API는 보통 1시간 전 데이터를 가장 최근으로 봄
    else: # 30분 발표 데이터
         base_dt_for_fcst = base_dt_for_fcst.replace(minute=30)


    # 1. 현재 실황 데이터 가져오기 (T1H: 기온, REH: 습도, WSD: 풍속)
    current_weather_items = get_weather_data(datetime.now(), "초단기실황") # 실황은 보통 정시 기준
    current_temp = None
    current_humidity = None
    current_windspeed = None

    if current_weather_items:
        for item in current_weather_items:
            if item["category"] == "T1H":
                current_temp = float(item["obsrValue"])
            elif item["category"] == "REH":
                current_humidity = float(item["obsrValue"])
            elif item["category"] == "WSD":
                current_windspeed = float(item["obsrValue"])

    if current_temp is None: # 실황 데이터 못가져오면 일단 중단
        print(f"{now.strftime('%Y-%m-%d %H:%M:%S')} - 현재 실황 데이터 수집 실패. 스크립트를 종료합니다.")
        return

    # 2. 1시간 뒤, 2시간 뒤, 3시간 뒤 예보 기온 가져오기
    forecast_items = get_weather_data(datetime.now(), "초단기예보") # 초단기예보는 가장 최근 발표 기준
    temp_after_1h = None

    if forecast_items:
        for item in forecast_items:
            forecast_time = datetime.strptime(base_dt_for_fcst.strftime('%Y%m%d') + item["fcstTime"], "%Y%m%d%H%M")
            time_diff_hours = (forecast_time - now).total_seconds() / 3600

            if item["category"] == "T1H": # 기온
                if 0.5 <= time_diff_hours < 1.5: # 약 1시간 뒤 예보
                    temp_after_1h = float(item["fcstValue"])
                # elif 1.5 <= time_diff_hours < 2.5: # 약 2시간 뒤 예보
                #     temp_after_2h = float(item["fcstValue"])
                # elif 2.5 <= time_diff_hours < 3.5: # 약 3시간 뒤 예보
                #     temp_after_3h = float(item["fcstValue"])

    # 3. 데이터 기록 (현재 + 미래 기온 데이터를 묶어서 1줄로 만들기)
    record_time = now.strftime("%Y-%m-%d %H:%M:%S")
    if temp_after_1h is not None: # 1시간 뒤 예보라도 있어야 저장
        new_row = {
            "측정시간": record_time,
            "현재기온": current_temp,
            "현재습도": current_humidity,
            "현재풍속": current_windspeed,
            "1시간뒤기온": temp_after_1h,
            # "2시간뒤기온": temp_after_2h,
            # "3시간뒤기온": temp_after_3h,
        }
        collected_data.append(new_row)
        print(f"{record_time} - 데이터 수집: 현재 {current_temp}°C, 1시간 뒤 예보 {temp_after_1h}°C")
    else:
        print(f"{record_time} - 1시간 뒤 예보 기온 수집 실패.")


    # 4. CSV 파일에 저장 (기존 파일이 있으면 덧붙이기)
    df_new = pd.DataFrame(collected_data)
    if not df_new.empty:
        if os.path.exists(CSV_FILE_PATH):
            df_existing = pd.read_csv(CSV_FILE_PATH)
            df_to_save = pd.concat([df_existing, df_new], ignore_index=True)
        else:
            df_to_save = df_new
        df_to_save.to_csv(CSV_FILE_PATH, index=False, encoding='utf-8-sig')
        print(f"데이터가 {CSV_FILE_PATH} 에 저장/업데이트 되었습니다.")


if __name__ == "__main__":
    # 지금 당장 2~3번 실행해서 데이터 몇 줄이라도 모으자!
    # 예: 1시간 간격으로 3번 실행
    for i in range(3): # 3시간 동안 데이터 수집 (테스트용)
        print(f"\n===== 데이터 수집 시도 {i+1}/3 =====")
        main()
        if i < 2: # 마지막 시도 후에는 대기 안 함
            print(f"다음 수집까지 1시간 대기합니다... (실제로는 약 {60*60}초 뒤에 다시 실행하세요)")
            # time.sleep(60*60) # 실제 운영시에는 1시간 대기
            print("실제 운영이 아니므로 바로 다음 수집을 시도합니다 (테스트 목적).")
            time.sleep(5) # 짧은 대기 후 바로 다음 시도 (테스트용)