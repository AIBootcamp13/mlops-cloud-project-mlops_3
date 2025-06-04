import requests
import os
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from io import StringIO
import boto3
import sys

# PYTHONPATH에 mlops_team 경로 추가 
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 상수 모듈 import 
try:
    from utils.constants import KMA_API_URL, WEATHER_COLUMNS
except ModuleNotFoundError:
    print("경고: utils.constants 모듈을 찾을 수 없습니다.")
    print("현 위치: ", os.getcwd())
    print("스크립트 위치: ", os.path.abspath(__file__))
    print("mlops_team/utils/constants.py 파일이 올바른 위치에 있는지,")
    print("WEATHER_COLUMNS 변수가 정의되어 있는지 확인하세요.")
    raise


# .env 파일 로드 및 AWS/S3 변수 설정 
dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '.env')
load_dotenv(dotenv_path=dotenv_path)

AUTH_KEY = os.getenv('AUTH_KEY')
S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME')
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_REGION = os.getenv('AWS_REGION')

TARGET_STATION_ID = '159' # 수집할 목표 지점 ID (부산)
TARGET_S3_PREFIX = "data/weather/realtime_hourly_raw" 



# 특정 KST 시간의 특정 지점 날씨 데이터를 KMA API로부터 가져와 DataFrame으로 반환.
# fetch_weather_data 함수를 기반으로 단일 시간 조회용으로 수정.
def fetch_single_hour_kma_data(target_kst_dt: datetime, station_id: str, auth_key: str):
    if not auth_key:
        print(f"오류: {target_kst_dt.strftime('%Y-%m-%d %H:%M')} KMA API 인증키(AUTH_KEY)가 없습니다.")
        return None
    if not WEATHER_COLUMNS:
        print(f"오류: {target_kst_dt.strftime('%Y-%m-%d %H:%M')} WEATHER_COLUMNS가 정의되지 않아 파싱 불가.")
        return None

    tm_value_str = target_kst_dt.strftime("%Y%m%d%H%M") # YYYYMMDDHHMM 형식

    api_params = {
        "tm1": tm_value_str,
        "tm2": tm_value_str,
        "stn": station_id,
        "authKey": auth_key,
    }
    
    print(f"KMA API 요청: 지점({station_id}), KST시간({target_kst_dt.strftime('%Y-%m-%d %H:%M')})")

    try:
        response = requests.get(KMA_API_URL, params=api_params, timeout=30) # 타임아웃 30초
        response.raise_for_status() # 4xx, 5xx 에러 시 예외 발생
        print(f"API 응답 상태 코드: {response.status_code}")
        
        try:
            raw_data = response.content.decode('EUC-KR')
            print("API 응답 EUC-KR 디코딩 성공.")
        except UnicodeDecodeError:
            print("경고: EUC-KR 디코딩 실패. 기본 response.text 사용.")
            raw_data = response.text

        # 데이터 라인만 추출 (주석 '#'으로 시작하는 줄 제외)
        data_lines = [line for line in raw_data.strip().split("\n") if not line.startswith("#")]
        if not data_lines:
            print("API 응답에서 유효한 데이터 라인을 찾을 수 없습니다.")
            return None

        # pd.read_csv를 사용하여 공백 기반으로 파싱
        df = pd.read_csv(
            StringIO("\n".join(data_lines)),
            sep=r'\s+', # 하나 이상의 연속된 공백을 구분자로
            header=None,
            names=WEATHER_COLUMNS, # utils.constants에서 가져온 컬럼명 리스트
            na_values=['-9', '-9.0', '-99', '-99.0', '-999', '-999.0'] # 결측치로 처리할 값들
        )
        print(f"KMA 데이터 파싱 성공: 총 {len(df)}줄, {len(df.columns)}개 컬럼.")
        
        # ObservationTime을 datetime 객체로 변환
        if 'ObservationTime' in df.columns:
            # KMA API의 첫번째 필드(YYMMDDHHMI)가 숫자로 읽힐 수 있으므로, astype(str)로 먼저 변환
            df['ObservationTime'] = pd.to_datetime(df['ObservationTime'].astype(str), format='%Y%m%d%H%M', errors='coerce')
            df.dropna(subset=['ObservationTime'], inplace=True) # 변환 실패한 행(NaT)이 있다면 제거
            if df.empty:
                print("시간 변환 후 유효한 데이터가 없습니다.")
                return None
        else:
            print("경고: DataFrame에 'ObservationTime' 컬럼이 없습니다. WEATHER_COLUMNS 정의를 확인하세요.")
            # ObservationTime이 없으면 S3 경로 생성이 어려우므로 None 반환 또는 에러 처리
            return None
            
        # StationID도 일관성을 위해 문자열로 변경 
        if 'StationID' in df.columns:
            df['StationID'] = df['StationID'].astype(str)
            
        return df

    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP 오류: {http_err}, 응답 코드: {http_err.response.status_code if http_err.response else 'N/A'}")
    except requests.exceptions.RequestException as req_err:
        print(f"요청 오류: {req_err}")
    except Exception as e:
        print(f"데이터 처리 중 알 수 없는 오류: {e}")
    return None



# DataFrame을 시간별로 나뉜 CSV로 S3에 업로드.
def save_hourly_data_to_s3_csv(df: pd.DataFrame, observation_kst_dt: datetime, 
                               bucket_name: str, s3_prefix: str, 
                               aws_access_key: str, aws_secret_key: str, aws_region: str):
    if df is None or df.empty:
        print("S3에 업로드할 데이터가 없습니다.")
        return False

    year = observation_kst_dt.strftime("%Y")
    month = observation_kst_dt.strftime("%m")
    day = observation_kst_dt.strftime("%d")
    hour = observation_kst_dt.strftime("%H")

    s3_key = f"{s3_prefix}/year={year}/month={month}/day={day}/hour={hour}/data.csv"
    
    try:
        csv_buffer = StringIO()
        df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
        csv_content = csv_buffer.getvalue()

        s3_client = boto3.client('s3',
                                 aws_access_key_id=aws_access_key,
                                 aws_secret_access_key=aws_secret_key,
                                 region_name=aws_region)
        s3_client.put_object(Bucket=bucket_name, Key=s3_key, Body=csv_content)
        print(f"CSV 파일 업로드 성공: s3://{bucket_name}/{s3_key}")
        return True
    except Exception as e:
        print(f"S3 CSV 업로드 중 오류 발생: {e}")
        return False


# 1시간 전의 날씨 데이터를 수집하여 S3에 CSV로 저장하는 메인 작업.
def collect_single_hour_weather_job():
    kst_tz = timezone(timedelta(hours=9))
    current_kst_time = datetime.now(kst_tz)
    target_dt_for_data_kst = current_kst_time.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    
    print(f"\n--- 시간별 날씨 데이터 수집 작업 시작 ({current_kst_time.strftime('%Y-%m-%d %H:%M:%S KST')}) ---")
    print(f"수집 대상 KST 기준 시간: {target_dt_for_data_kst.strftime('%Y-%m-%d %H:%M')}")

    # 1. KMA 데이터 가져오기 (모든 컬럼, 부산 지점)
    df_weather_hour = fetch_single_hour_kma_data(
        target_dt_for_data_kst, 
        station_id=TARGET_STATION_ID,  
        auth_key=AUTH_KEY            
    )


    if df_weather_hour is not None and not df_weather_hour.empty:
        print("\n--- KMA API로부터 받은 데이터 (1시간 분량) ---")
        print(f"데이터 건수: {len(df_weather_hour)}")
        df_weather_hour.info()
        print(df_weather_hour.head())
        
        actual_observation_time = df_weather_hour['ObservationTime'].iloc[0] 
        
        # 디버깅 코드 (유용하니 남겨두자)
        print(f"\nDEBUG: actual_observation_time의 타입: {type(actual_observation_time)}")
        print(f"DEBUG: actual_observation_time의 값: {actual_observation_time}\n")

        # 2. S3에 국현님이 요청한대로 CSV로 저장
        save_hourly_data_to_s3_csv(
            df_weather_hour,         # 1. df
            actual_observation_time, # 2. observation_kst_dt (datetime 객체)
            S3_BUCKET_NAME,          # 3. bucket_name (문자열)
            TARGET_S3_PREFIX,        # 4. s3_prefix (문자열)
            AWS_ACCESS_KEY_ID,       # 5. aws_access_key
            AWS_SECRET_ACCESS_KEY,   # 6. aws_secret_key
            AWS_REGION               # 7. aws_region
        )
    else:
        print("데이터를 가져오지 못했거나 처리 중 오류가 발생하여 S3에 저장할 수 없습니 다.")
    print(f"--- 시간별 날씨 데이터 수집 작업 종료 ({datetime.now(kst_tz).strftime('%Y-%m-%d %H:%M:%S KST')}) ---")
    
if __name__ == "__main__":
    # 필수 환경 변수 존재 여부 확인
    required_env_vars = ['AUTH_KEY', 'S3_BUCKET_NAME', 'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_REGION']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    constants_loaded = 'WEATHER_COLUMNS' in globals() and WEATHER_COLUMNS # WEATHER_COLUMNS가 로드되었는지 확인
    
    if missing_vars:
        print(f"오류: 다음 필수 환경 변수가 .env 파일에 설정되지 않았습니다: {', '.join(missing_vars)}")
    elif not constants_loaded:
        print("오류: utils.constants 에서 WEATHER_COLUMNS를 로드하지 못했습니다. 파일 경로 및 내용을 확인하세요.")
    else:
        collect_single_hour_weather_job()