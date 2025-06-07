import requests
from io import StringIO
import pandas as pd
import requests
from tqdm import tqdm
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
import s3fs
import os
import sys
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)
from data.utils.constants import (
    KMA_STATION_ID,
    KMA_API_URL,
    WEATHER_COLUMNS,
    WEATHER_KOREAN_COLUMNS,
    LOOKBACK_DAYS,
)

load_dotenv()

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info("This will be printed in terminal")

# AWS 자격 증명 확인
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_DEFAULT_REGION = os.getenv('AWS_DEFAULT_REGION')
S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME')

def fetch_weather_data(start_datetime: str, end_datetime: str) -> pd.DataFrame:
    """
    기상청 API에서 날씨 데이터를 가져옵니다.
    
    Args:
        start_datetime (str): 시작 날짜/시간 (YYYYMMDDHHMM 형식)
        end_datetime (str): 종료 날짜/시간 (YYYYMMDDHHMM 형식)
    
    Returns:
        pd.DataFrame: 가져온 날씨 데이터
    """
    api_params = {
        "tm1": start_datetime,
        "tm2": end_datetime,
        "stn": KMA_STATION_ID,
        "authKey": os.getenv('AUTH_KEY'),
        "help": 0
    }
    
    response = requests.get(KMA_API_URL, params=api_params)
    raw_data = response.text
    
    use_korean_columns = False
    
    data_lines = [line for line in raw_data.strip().split("\n") if not line.startswith("#")]
    
    return pd.read_csv(
        StringIO("\n".join(data_lines)),
        sep=r'\s+',
        header=None,
        names= WEATHER_KOREAN_COLUMNS if use_korean_columns else WEATHER_COLUMNS
    )

def generate_date_ranges(start_date: datetime, end_date: datetime) -> list:
    """
    주어진 기간을 BATCH_DAYS 단위로 나누어 날짜 범위 리스트를 생성합니다.
    
    Args:
        start_date (datetime): 시작 날짜
        end_date (datetime): 종료 날짜
    
    Returns:
        list: (시작날짜, 종료날짜) 튜플의 리스트
    """
    start_date = start_date.replace(minute=0, second=0, microsecond=0)
    end_date = end_date.replace(minute=0, second=0, microsecond=0)

    date_ranges = []
    current_start = start_date

    while current_start <= end_date:
        current_end = min(current_start + timedelta(days=LOOKBACK_DAYS), end_date)
        current_end = current_end.replace(hour=23)

        start_str = current_start.strftime('%Y%m%d%H%M')
        end_str = current_end.strftime('%Y%m%d%H%M')

        date_ranges.append((start_str, end_str))
        current_start = current_end + timedelta(hours=1)
    
    return date_ranges

def get_latest_weather_data() -> datetime:
    """
    S3에서 가장 최근 날씨 데이터의 시간을 가져옵니다.
    파일 경로의 마지막 날짜와 parquet 파일 내의 마지막 시간을 모두 확인합니다.
    """
    s3 = s3fs.S3FileSystem()
    try:
        # S3 버킷에서 가장 최근 데이터 파일 찾기
        files = s3.glob(f"{S3_BUCKET_NAME}/data/weather/raw/*/*/*/data.parquet")
        if not files:
            return datetime(2000, 1, 1)
        
        # 파일 경로에서 날짜 정보 추출
        latest_file = max(files)
        
        # 해당 날짜의 parquet 파일에서 마지막 시간 확인
        df = pd.read_parquet(latest_file, filesystem=s3)
        last_time = pd.to_datetime(df['ObservationTime']).max()
        return last_time
            
    except Exception as e:
        print(f"S3에서 최신 데이터 확인 중 오류 발생: {e}")
        return datetime(2000, 1, 1)

def save_to_s3(df: pd.DataFrame, year: int, month: int, day: int):
    """
    데이터프레임을 S3에 저장합니다.
    """
    s3 = s3fs.S3FileSystem()
    path = f"{S3_BUCKET_NAME}/data/weather/raw/year={year:04d}/month={month:02d}/day={day:02d}/data.parquet"
    try:
        df.to_parquet(path, index=False, engine='pyarrow', filesystem=s3)
    except Exception as e:
        print(f"S3 저장 중 오류 발생: {e}")

def initialize_weather_database():
    """
    전체 날씨 데이터를 가져와 S3에 저장합니다.
    """
    start_date = datetime(2000, 1, 1)
    end_date = datetime.now()
    date_ranges = generate_date_ranges(start_date, end_date)
    
    weather_data_frames = []
    for start_time, end_time in tqdm(date_ranges, desc="날씨 데이터 수집 중"):
        weather_data_frames.append(fetch_weather_data(start_time, end_time))
    
    combined_data = pd.concat(weather_data_frames)
    combined_data['ObservationTime'] = pd.to_datetime(combined_data['ObservationTime'], format='%Y%m%d%H%M')
    combined_data['year'] = combined_data['ObservationTime'].dt.year
    combined_data['month'] = combined_data['ObservationTime'].dt.month
    combined_data['day'] = combined_data['ObservationTime'].dt.day
    combined_data['hour'] = combined_data['ObservationTime'].dt.hour
    
    # 일별로 데이터를 나누어 S3에 저장
    for (year, month, day), group_df in tqdm(combined_data.groupby(['year', 'month', 'day'])):
        group_df.drop(columns=['year', 'month', 'day'], inplace=True)
        save_to_s3(group_df, year, month, day)

def update_weather_database():
    """
    S3의 최신 데이터 이후부터 현재까지의 날씨 데이터를 업데이트합니다.
    """
    last_observation = get_latest_weather_data()
    print("🔍 마지막 관측 시간:", last_observation)  # 추가!

    start_time = last_observation + timedelta(hours=1)
    end_time = datetime.now()
    
    if start_time >= end_time:
        print("이미 최신 데이터가 있습니다.")
        return
    
    date_ranges = generate_date_ranges(start_time, end_time)
    weather_data_frames = []
    
    for start_time, end_time in tqdm(date_ranges, desc="날씨 데이터 업데이트 중"):
        weather_data_frames.append(fetch_weather_data(start_time, end_time))
    
    if weather_data_frames:
        new_data = pd.concat(weather_data_frames)
        new_data['ObservationTime'] = pd.to_datetime(new_data['ObservationTime'], format='%Y%m%d%H%M')
        new_data['year'] = new_data['ObservationTime'].dt.year
        new_data['month'] = new_data['ObservationTime'].dt.month
        new_data['day'] = new_data['ObservationTime'].dt.day
        new_data['hour'] = new_data['ObservationTime'].dt.hour
        
        # 일별로 데이터를 나누어 S3에 저장
        for (year, month, day), group_df in new_data.groupby(['year', 'month', 'day']):
            group_df.drop(columns=['year', 'month', 'day'], inplace=True)
            save_to_s3(group_df, year, month, day)

def check_s3_path_exists() -> bool:
    """
    S3에 weather 데이터 경로가 존재하는지 확인합니다.
    """
    s3 = s3fs.S3FileSystem()
    try:
        # weather 폴더가 있는지 확인
        weather_path = f"{S3_BUCKET_NAME}/data/weather/raw"
        return s3.exists(weather_path) and len(s3.ls(weather_path)) > 0
    except Exception as e:
        print(f"S3 경로 확인 중 오류 발생: {e}")
        return False

def collect_weather_data_with_time():
    """
    S3에 weather 데이터가 없으면 초기화하고, 있으면 업데이트합니다.
    """
    if check_s3_path_exists():
        print("기존 날씨 데이터가 발견되어 업데이트를 시작합니다.")
        update_weather_database()
    else:
        print("기존 날씨 데이터가 없어 초기화를 시작합니다.")
        initialize_weather_database()

if __name__ == "__main__":
    collect_weather_data_with_time()
    
    
    
    
    
    
    
