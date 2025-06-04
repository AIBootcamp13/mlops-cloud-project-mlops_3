import pandas as pd
import numpy as np
import warnings
import time
import tempfile
import s3fs
import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from scipy.stats import shapiro, spearmanr, kruskal
from sklearn.preprocessing import LabelEncoder
warnings.filterwarnings('ignore')

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Feature_Engineering:
    def __init__(self, df=None):
        self.df = df
        self.label_encoders = {}
        self.s3_bucket = os.getenv("S3_BUCKET_NAME")
        self.s3 = s3fs.S3FileSystem()
        logger.info("Feature Engineering pipeline initialized")

        # 디버그 위해 추가
        logger.info(f"Loaded S3_BUCKET_NAME: {os.getenv('S3_BUCKET_NAME')}")

        """S3에서 parquet 파일을 로드"""
    def load_data_from_s3(self, year, month, day):
        path = f"{self.s3_bucket}/data/weather/preprocess/v1.0.0/2025.04.30_0000_2025.05.29_1200.parquet"

        try:
            logger.info(f"Loading data from S3: {path}")
            
            self.df = pd.read_parquet(path, filesystem=self.s3)
            logger.info(f"Data loaded successfully. Shape: {self.df.shape}")
            logger.info(f"Columns in the dataset: {self.df.columns.tolist()}")
            return self.df
            
        except Exception as e:
            logger.error(f"Error loading data: {str(e)}")
            raise

    def save_to_s3(self, df, version='v1.0.0'):
        """전처리된 데이터를 S3에 저장"""
        try:
            # 파일명 생성 (현재 시간 기준)
            current_time = datetime.now()
            filename = f"{current_time.strftime('%Y.%m.%d_%H%M')}.parquet"
            
            # S3 경로 생성
            path = f"{self.s3_bucket}/data/weather/preprocess/{version}/{filename}"
            
            logger.info(f"Saving processed data to S3: {path}")
            
            # S3에 직접 저장
            df.to_parquet(
                path,
                index=False,
                engine='pyarrow',
                filesystem=self.s3
            )
            
            logger.info("Data saved successfully")
            return path
            
        except Exception as e:
            logger.error(f"Error saving data: {str(e)}")
            raise

    def missing_value(self):
        """결측치를 처리"""
        logger.info("Processing missing values")
        for col in self.df.columns:
            if '-' in self.df[col].values:
                self.df[col] = self.df[col].replace('-', 'Other')
        logger.info("Missing value processing completed")
        return self.df

    def spearman_test(self, target_col):
        df_num = self.df.select_dtypes(include=['number'])
        features = []
        correlations = []
        p_values = []

        for col in df_num.columns:
            if col != target_col:
                corr, p = spearmanr(df_num[target_col], df_num[col])
                features.append(col)
                correlations.append(corr)
                p_values.append(p)

        corr_df = pd.DataFrame({
            'Feature': features,
            'Correlation': correlations,
            'P-value': p_values}).sort_values(by='Correlation', ascending=False).reset_index(drop=True)

        p_value_over_05 = corr_df[corr_df['P-value'] >= 0.05]['Feature'].tolist() # 유의하지 않은 변수
        return p_value_over_05
    

    def remove_high_corr_target(self, target_col, threshold=0.95, method='spearman'):
        feats = self.df.select_dtypes(include=[np.number]).columns.drop(target_col)
        corr_feats = self.df[feats].corr(method=method).abs()
        corr_target = self.df[feats].corrwith(self.df[target_col], method=method).abs()
        
        to_drop = set()
        for i, f1 in enumerate(feats):
            for f2 in feats[i+1:]:
                # 0.95 초과인 경우
                if corr_feats.loc[f1, f2] > threshold:
                    if corr_target[f1] >= corr_target[f2]:
                        to_drop.add(f2)
                    else:
                        to_drop.add(f1)
        return list(to_drop) 


    def kruskal_test(self, target_col, min_group_size=5):
        cat_cols = self.df.select_dtypes(include=['object','category']).columns.tolist()
        results = []

        for col in cat_cols:
            grouped = self.df.groupby(col)[target_col]
            valid_groups = [grp.values for _, grp in grouped if grp.size >= min_group_size]
            if len(valid_groups) >= 2:
                stat, p = kruskal(*valid_groups)
                results.append({'feature': col, 'H-statistic': stat, 'p-value': p})

        kruskal_df = pd.DataFrame(results).sort_values('p-value').reset_index(drop=True)
        kruskal_cols = kruskal_df[kruskal_df['p-value'] >= 0.05]['feature'].tolist() # 유의미하지 않은 변수
        return kruskal_cols


    # 위에서 사용한 검정을 통해 최종 피쳐 선택
    # 확인했을 때 최종 선택된 피쳐 수: 34개!!
    def feature_selection(self, target_col):
        spearman_over_05 = self.spearman_test(target_col) # 스피어만 검정에서 유의하지 않은 변수
        corr_over_95 = self.remove_high_corr_target(target_col) # 변수간 상관계수가 0.95 초과인 변수
        kruskal_over_05 = self.kruskal_test(target_col) # 크루스칼 검정에서 유의하지 않은 변수
        exclude_cols = ['WeatherCode', 'StationID', 'ObservationTime'] # 필요 없는 변수
        drop_cols = spearman_over_05 + corr_over_95 + kruskal_over_05 + exclude_cols # 최종 제거 변수

        # year, month, day, hour 컬럼은 제거하지 않음
        for col in ['year', 'month', 'day', 'hour']:
            if col in drop_cols:
                drop_cols.remove(col)

        # 실제로 존재하는 컬럼만 제거
        drop_cols = [col for col in drop_cols if col in self.df.columns]
        self.df = self.df.drop(columns=drop_cols) # 최종 제거

        # order_cols 중 실제로 존재하는 컬럼만 사용
        order_cols = ['year', 'month', 'day', 'hour', 'Temperature']
        existing_order_cols = [col for col in order_cols if col in self.df.columns]
        remaining_cols = [col for col in self.df.columns if col not in existing_order_cols]
        
        self.df = self.df[existing_order_cols + remaining_cols] # 순서 재배치
        return self.df


    # 계절변수 생성
    def add_season_feature(self):
        def get_season(month):
            if 3 <= month <= 5:
                return 'Spring'
            elif 6 <= month <= 8:
                return 'Summer'
            elif 9 <= month <= 11:
                return 'Fall'
            else:
                return 'Winter'
            
        self.df['season'] = self.df['month'].apply(get_season)
        return self.df


    def encoding(self):
        if 'CloudType' in self.df.columns: # 라벨 인코딩
            le = LabelEncoder()
            self.df['CloudType_encoded'] = le.fit_transform(self.df['CloudType'])
            self.label_encoders['CloudType'] = le
            self.df = self.df.drop(columns=['CloudType'])

        if 'season' in self.df.columns: # 원-핫 인코딩
            # self.df = pd.get_dummies(self.df, columns=['season'], drop_first=False).astype(int)
            self.df = pd.get_dummies(self.df, columns=['season'], drop_first=False, dtype=int)
            # FIXME : 홍정민 수정함. astype(int)에서 'Other'가 int로 변환되지 않아 df 전체를 정수로 형변환하지 않는 방식으로 수정함.

        return self.df

    # 타겟 변수: 1시간 뒤의 temperature
    def target_temp(self):
        self.df = self.df.sort_values(by=['year', 'month', 'day', 'hour']) # 정렬
        self.df['target_temp'] = self.df['Temperature'].shift(-1)  # 1시간 뒤 온도를 타겟으로
        self.df = self.df.dropna(subset=['target_temp'])  # 마지막 row는 타겟이 없으니 제거

        return self.df
    
