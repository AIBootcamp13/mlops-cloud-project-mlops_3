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

    def load_data_from_s3(self, year, month, day):
        """S3에서 parquet 파일을 로드"""
        try:
            path = f"{self.s3_bucket}/data/weather/raw/{year}/{month}/{day}/data.parquet"
            logger.info(f"Loading data from S3: {path}")
            
            self.df = pd.read_parquet(path, filesystem=self.s3)
            logger.info(f"Data loaded successfully. Shape: {self.df.shape}")
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


    def feature_selection(self, target_col):
        spearman_over_05 = self.spearman_test(target_col) # 스피어만 검정에서 유의하지 않은 변수
        corr_over_95 = self.remove_high_corr_target(target_col) # 변수간 상관계수가 0.95 초과인 변수
        kruskal_over_05 = self.kruskal_test(target_col) # 크루스칼 검정에서 유의하지 않은 변수
        exclude_cols = ['WeatherCode', 'StationID', 'ObservationTime'] # 필요 없는 변수
        drop_cols = spearman_over_05 + corr_over_95 + kruskal_over_05 + exclude_cols # 최종 제거 변수

        for col in drop_cols:
            if col == 'day':
                drop_cols.remove(col)

        self.df = self.df.drop(columns=drop_cols) # 최종 제거
        order_cols = ['year', 'month', 'day', 'hour', 'Temperature']
        self.df = self.df[order_cols + [c for c in self.df.columns if c not in order_cols]] # 순서 재배치
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
            self.df = pd.get_dummies(self.df, columns=['season'], drop_first=False).astype(int)

        return self.df


    def target_temp(self):
        self.df = self.df.sort_values(by=['year', 'month', 'day', 'hour']) # 정렬
        self.df['target_temp'] = self.df['Temperature'].shift(-1)  # 1시간 뒤 온도를 타겟으로
        self.df = self.df.dropna(subset=['target_temp'])  # 마지막 row는 타겟이 없으니 제거

        return self.df
    

def main():
    try:
        # Feature_Engineering 인스턴스 생성
        fe = Feature_Engineering()
        
        # 테스트용 데이터 로드 (예: 2022년 21월 01일 데이터)
        df = fe.load_data_from_s3(year='2022', month='21', day='01')
        
        # 전처리 파이프라인 실행
        df = fe.missing_value()  # 1. 결측치 처리
        df = fe.feature_selection('Temperature')  # 2. 특성 선택
        df = fe.add_season_feature()  # 3. 계절 변수 추가
        df = fe.encoding()  # 4. 인코딩
        df = fe.target_temp()  # 5. 타겟 변수 생성
        
        # 전처리된 데이터를 S3에 저장
        path = fe.save_to_s3(df, version='v1.0.0')
        
        logger.info("Feature engineering pipeline completed")
        logger.info(f"Processed data saved at: {path}")
        
    except Exception as e:
        logger.error(f"Pipeline error: {str(e)}")
        raise

if __name__ == "__main__":
    main()
    

