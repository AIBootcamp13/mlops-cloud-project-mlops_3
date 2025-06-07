import os
import pandas as pd
from datetime import datetime, timedelta
import s3fs
from tqdm import tqdm
from data.utils.constants import LOOKBACK_DAYS
from dotenv import load_dotenv
load_dotenv()

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info("This will be printed in terminal")


S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME')
class WeatherPreprocess:
    def __init__(self):
        super().__init__()
        self.preprocess_version = "v1.0.0"
        self.preprocess_data()

    def preprocess_data(self):
        """날씨 데이터 전처리 메인 메서드"""
        df = self.load()
        df = self.convert_data_types(df)
        self.save(df)

    def load(self):
        """S3에서 날씨 데이터를 로드합니다."""
        s3 = s3fs.S3FileSystem()
        
        # 현재 날짜 기준으로 검색
        current_date = datetime.now()
        dt_minus = current_date - timedelta(days=LOOKBACK_DAYS)
        
        # 날짜 범위 생성
        date_range = pd.date_range(start=dt_minus, end=current_date, freq='D')
        
        print("날씨 데이터 로드 중...")
        print(f"검색 기간: {dt_minus.strftime('%Y-%m-%d')} ~ {current_date.strftime('%Y-%m-%d')}")
        
        dfs = []
        for date in tqdm(date_range, desc="날짜별 데이터 로드 중"):
            year = date.year
            month = date.month
            day = date.day
            
            file_path = f"{S3_BUCKET_NAME}/data/weather/raw/year={year}/month={month:02d}/day={day:02d}/data.parquet"
            try:
                if s3.exists(file_path):
                    df = pd.read_parquet(file_path, filesystem=s3)
                    dfs.append(df)
            except Exception as e:
                print(f"파일 로드 실패 ({file_path}): {str(e)}")
                continue
        
        if not dfs:
            raise ValueError("날씨 데이터를 찾을 수 없습니다.")
            
        combined_df = pd.concat(dfs)
        print(f"로드된 데이터 기간: {combined_df['ObservationTime'].min()} ~ {combined_df['ObservationTime'].max()}")
        return combined_df

    def save(self, preprocessed_data: pd.DataFrame):
        """전처리된 데이터를 S3에 저장합니다."""
        s3 = s3fs.S3FileSystem()
        
        # 데이터의 시작일과 종료일 가져오기
        start_date = preprocessed_data['ObservationTime'].min()
        end_date = preprocessed_data['ObservationTime'].max()
        
        # 저장 경로 설정
        save_path = f"{S3_BUCKET_NAME}/data/weather/preprocess/{self.preprocess_version}/{start_date.strftime('%Y.%m.%d_%H%M')}_{end_date.strftime('%Y.%m.%d_%H%M')}.parquet"
        
        try:
            preprocessed_data.to_parquet(save_path, index=False, engine='pyarrow', filesystem=s3)
            print(f"전처리된 데이터가 저장되었습니다: {save_path}")
            print(f"데이터 기간: {start_date.strftime('%Y-%m-%d %H:%M')} ~ {end_date.strftime('%Y-%m-%d %H:%M')}")
        except Exception as e:
            print(f"데이터 저장 중 오류 발생: {e}")

    def convert_data_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """데이터 타입 변환"""
        return df
    
if __name__ == "__main__":
    WeatherPreprocess()
