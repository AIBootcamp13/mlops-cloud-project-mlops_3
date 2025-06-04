import requests
import os
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime, timedelta
from io import StringIO # 텍스트 데이터를 파일처럼 다루기 위해
import numpy as np # 결측치 처리를 위해
import boto3 # S3 업로드를 위해

# .env 파일 경로 설정 (프로젝트 루트에 .env 파일이 있다고 가정)
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=dotenv_path)

# 환경 변수에서 설정값 가져오기
AUTH_KEY = os.getenv('AUTH_KEY')
KMA_API_URL = 'https://apihub.kma.go.kr/api/typ01/url/kma_sfctm3.php' # 고정
S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME')
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_REGION = os.getenv('AWS_REGION')

def fetch_weather_data_text(target_dt):
    """특정 시간의 날씨 데이터를 KMA API로부터 텍스트 형태로 가져옵니다."""
    if not AUTH_KEY:
        print("AUTH_KEY가 설정되지 않았습니다.")
        return None

    tm_value = target_dt.strftime("%Y%m%d%H%M") # YYYYMMDDHHMM (분 단위까지)

    params = {
        'authKey': AUTH_KEY,
        'pageNo': 1,
        'numOfRows': 100, # 특정 시간, 특정 지점 데이터는 보통 1개. 여러 지점 고려 시 조절.
        # 'stnIds': '159',  # 부산 지점. 필요에 따라 파라미터로 받거나 설정
        'tm1': tm_value,
        'tm2': tm_value,
    }
    print(f"KMA API 요청: 지점(모든 관측지), 시간({tm_value})")

    try:
        response = requests.get(KMA_API_URL, params=params, timeout=30) # 타임아웃 늘림
        response.raise_for_status() # 오류 발생 시 예외 발생
        print(f"API 응답 상태 코드: {response.status_code}")
        return response.text
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP 오류 발생: {http_err}, 응답: {response.text if response else '응답 없음'}")
    except requests.exceptions.RequestException as req_err:
        print(f"요청 중 오류 발생: {req_err}")
    return None

def parse_kma_text_data(text_data):
    """KMA API 텍스트 응답을 Pandas DataFrame으로 파싱합니다."""
    if not text_data:
        return None

    lines = text_data.strip().split('\n')
    
    header_line_index = -1
    column_header = []
    data_lines = []

    for i, line in enumerate(lines):
        if line.startswith('# YYMMDDHHMI'): # 실제 컬럼명이 있는 라인 찾기
            header_line_index = i
            # 공백이 여러 개인 것을 기준으로 split 하고, 빈 문자열 제거
            column_header = [col for col in line[1:].strip().split(' ') if col] # 맨 앞 # 제거
            break
    
    if not column_header:
        print("컬럼 헤더를 찾을 수 없습니다.")
        return None

    # 컬럼 헤더 다음 라인부터 데이터 라인으로 간주 (단위 라인은 건너뜀)
    # 실제 데이터는 헤더라인 + 단위라인 다음부터 시작되므로 +2 (또는 그 이상)
    # 하지만, 더 간단하게는 #로 시작하지 않는 라인을 데이터로 간주
    for line in lines[header_line_index + 2:]: # 헤더, 단위 다음부터
        if not line.startswith('#') and line.strip(): # 주석 아니고 비어있지 않은 라인
            data_lines.append(line)
            
    if not data_lines:
        print("데이터 라인을 찾을 수 없습니다.")
        return None

    # 데이터 라인들을 StringIO를 사용해 파일처럼 만들어 read_csv로 읽기
    # 구분자는 여러 개의 공백일 수 있으므로 delim_whitespace=True 사용
    data_io = StringIO('\n'.join(data_lines))
    
    try:
        df = pd.read_csv(data_io, delim_whitespace=True, header=None, names=column_header, na_values=['-9', '-9.0', '-99', '-99.0'])
        print("데이터 파싱 성공!")
        return df
    except Exception as e:
        print(f"Pandas 파싱 중 오류: {e}")
        # 파싱 실패 시, 첫 몇 줄과 컬럼 헤더를 보여주면 디버깅에 도움
        print("파싱 시도한 컬럼:", column_header)
        print("파싱 시도한 데이터 (첫 5줄):")
        for l in data_lines[:5]:
            print(l)
        return None


def upload_df_to_s3(df, bucket_name, s3_key_prefix, target_dt):
    """DataFrame을 Parquet으로 S3에 업로드합니다 (년/월/일/시 파티셔닝)."""
    if df is None or df.empty:
        print("업로드할 데이터가 없습니다.")
        return

    year = target_dt.strftime("%Y")
    month = target_dt.strftime("%M") # 오타 수정: %m 이어야 함
    day = target_dt.strftime("%d")
    hour = target_dt.strftime("%H")

    # S3 저장 경로 (예: data/weather/hourly/year=2025/month=06/day=02/hour=14/data.parquet)
    s3_key = f"{s3_key_prefix}/year={year}/month={month}/day={day}/hour={hour}/data.parquet" # month=%M 오타 수정
    
    # DataFrame을 Parquet 형식의 바이트 스트림으로 변환
    try:
        parquet_buffer = StringIO() # 실제로는 BytesIO 사용해야 함
        # df.to_parquet(parquet_buffer, engine='pyarrow', index=False) # StringIO는 텍스트용
        
        # 올바른 방식: BytesIO 사용
        from io import BytesIO
        parquet_bytes_buffer = BytesIO()
        df.to_parquet(parquet_bytes_buffer, engine='pyarrow', index=False)
        parquet_bytes_buffer.seek(0)

        s3_client = boto3.client('s3', aws_access_key_id=AWS_ACCESS_KEY_ID, 
                                 aws_secret_access_key=AWS_SECRET_ACCESS_KEY, region_name=AWS_REGION)
        s3_client.put_object(Bucket=bucket_name, Key=s3_key, Body=parquet_bytes_buffer.getvalue())
        print(f"파일이 성공적으로 S3에 업로드되었습니다: s3://{bucket_name}/{s3_key}")
    except Exception as e:
        print(f"S3 업로드 중 오류 발생: {e}")


def main_job():
    # Airflow에서 실행될 때는 Airflow의 {{ ds }} 또는 {{ execution_date }} 등을 활용하여 target_dt 결정
    # 여기서는 테스트를 위해 현재 시간의 1시간 전으로 설정
    # KMA 자료는 보통 10~15분 정도 지연되어 올라오므로, 너무 현재 시각으로 하면 자료가 없을 수 있음.
    # 예를 들어, 14시에 실행한다면 13:00 ~ 13:59 사이의 데이터를 가져오기 위해 13시를 타겟으로 함.
    # KMA API가 HHMM 이므로, 정시 데이터를 원하면 HH00으로 설정
    execution_time_utc = datetime.utcnow() # Airflow는 UTC 기준
    execution_time_kst = execution_time_utc + timedelta(hours=9) # KST로 변환

    # 보통 한 시간 전 정시 데이터를 목표로 함
    target_kst_time_for_data = execution_time_kst.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    print(f"데이터 수집 대상 KST 시간: {target_kst_time_for_data.strftime('%Y-%m-%d %H:%M')}")

    weather_text = fetch_weather_data_text(target_kst_time_for_data)

    if weather_text:
        weather_df = parse_kma_text_data(weather_text)
        if weather_df is not None and not weather_df.empty:
            print("\n--- 파싱된 DataFrame 샘플 ---")
            print(weather_df.head())
            
            # 필요한 컬럼만 선택 (예시 - 실제 API 응답 보고 결정해야 함)
            # 예: 'YYMMDDHHMI', 'STN', 'TA', 'HM', 'RN' 등
            # selected_columns = ['YYMMDDHHMI', 'STN', 'TA', 'HM', 'RN'] # 실제 컬럼명으로 변경
            # try:
            #     weather_df_selected = weather_df[selected_columns]
            # except KeyError as e:
            #     print(f"선택한 컬럼을 찾을 수 없습니다: {e}. 사용 가능한 컬럼: {weather_df.columns.tolist()}")
            #     weather_df_selected = weather_df # 일단 전체 사용
            
            # 데이터 타입 변환 (예시 - 실제 데이터 보고 결정해야 함)
            # weather_df_selected['TA'] = pd.to_numeric(weather_df_selected['TA'], errors='coerce')
            # weather_df_selected['HM'] = pd.to_numeric(weather_df_selected['HM'], errors='coerce')
            # ...

            # S3 업로드
            s3_path_prefix = "data/weather/hourly" # 기존에 정했던 경로
            upload_df_to_s3(weather_df, S3_BUCKET_NAME, s3_path_prefix, target_kst_time_for_data)
        else:
            print("DataFrame 파싱에 실패했거나 데이터가 없습니다.")

if __name__ == "__main__":
    print("날씨 데이터 수집 및 S3 업로드 작업을 시작합니다.")
    main_job()
    print("작업 완료.")