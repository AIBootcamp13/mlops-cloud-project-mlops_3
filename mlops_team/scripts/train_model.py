import pandas as pd
import numpy as np
import pickle
import os
import time
import mlflow
import mlflow.sklearn
from typing import Dict, List, Tuple
from datetime import datetime
from sklearn.metrics import mean_squared_error
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor, ExtraTreesRegressor, HistGradientBoostingRegressor
from lightgbm import LGBMRegressor
from xgboost import XGBRegressor
from catboost import CatBoostRegressor
import argparse
import tempfile

import s3fs
import logging 


# 'scripts' 디렉토리가 없으면 자동으로 생성
os.makedirs("scripts", exist_ok=True)

class Tree_Models:
    def __init__(self, data_path: str, experiment_name: str = "weather_regression"):
        self.data_path = data_path
        self.experiment_name = experiment_name
        
        # MLflow 서버 설정 추가

        # test 06040104
        # mlflow.set_tracking_uri("http://localhost:5001")
        mlflow.set_tracking_uri("http://host.docker.internal:5001") 

        print(f"MLflow tracking URI: {mlflow.get_tracking_uri()}")
        
        # MLflow 실험 설정
        mlflow.set_experiment(self.experiment_name)
        print(f"Current experiment: {mlflow.get_experiment_by_name(self.experiment_name)}")
        
        # 트리 모델 정의
        tmp_dir = tempfile.mkdtemp()
        self.models = {
            'LightGBM': LGBMRegressor(n_estimators=100, learning_rate=0.1),
            'XGBoost': XGBRegressor(n_estimators=100, learning_rate=0.1, verbosity=0),
            'CatBoost': CatBoostRegressor(n_estimators=100, learning_rate=0.1, train_dir=tmp_dir, logging_level='Silent'),
            'RandomForest': RandomForestRegressor(n_estimators=100),
            'GradientBoosting': GradientBoostingRegressor(n_estimators=100, learning_rate=0.1),
            'ExtraTrees': ExtraTreesRegressor(n_estimators=100),
            'HistGradientBoosting': HistGradientBoostingRegressor(max_iter=100, learning_rate=0.1)}
        
        logging.info(f"Tree_Models initialized for data_path: {self.data_path}") # 디버그용 로그    

    # 기존의 국현님 코드
    # def load_data(self) -> Tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series]:
    #     """데이터를 로드하고 전처리합니다."""
    #     # 데이터 로드
    #     # df = pd.read_csv(self.data_path)
        
    #     # 시계열 정렬
    #     df = df.sort_values(by=['year', 'month', 'day', 'hour'])
        
    #     # target_temp 컬럼 생성 (1시간 뒤 온도)
    #     df['target_temp'] = df['Temperature'].shift(-1)
    #     df = df.dropna(subset=['target_temp'])
        
    #     # 학습/검증 데이터 분할
    #     train = df.iloc[:int(len(df) * 0.8)]
    #     val = df.iloc[int(len(df) * 0.8):]
        
    #     # 특성과 타겟 분리
    #     X_train = train.drop(columns=['Temperature', 'target_temp'])
    #     y_train = train['target_temp']
    #     X_val = val.drop(columns=['Temperature', 'target_temp'])
    #     y_val = val['target_temp']
        
    #     return X_train, y_train, X_val, y_val

    # 수정한 load_data 메소드
    # S3에서 전처리된 Parquet 데이터를 로드하고 학습/검증용으로 분할.
    def load_data(self) -> Tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series]:
        logging.info(f"Attempting to load preprocessed data from S3 path: {self.data_path}")
        
        # S3 경로 구성 (self.data_path가 '버킷명/경로/파일명.parquet' 형태라고 가정)
        full_s3_path = f"s3://{self.data_path}" 
        
        try:
            # Pandas가 s3fs와 pyarrow를 사용하여 S3에서 Parquet 파일을 직접 읽음
            df = pd.read_parquet(full_s3_path)
            logging.info(f"Successfully loaded data from {full_s3_path}. Shape: {df.shape}")
            logging.info(f"Columns from Parquet: {df.columns.tolist()}")
        except Exception as e:
            logging.error(f"Error loading data from {full_s3_path}: {e}")
            raise
        
        # 데이터가 비어있거나 컬럼이 없으면 예외 처리
        if 'target_temp' not in df.columns:
            logging.error("'target_temp' column not found in the preprocessed data from S3!")
            raise ValueError("'target_temp' column not found in the preprocessed data from S3!")
        if 'Temperature' not in df.columns and 'target_temp' in df.columns : 
            logging.warning("'Temperature' column not found. Will proceed if not strictly needed for X features.")


        # 학습/검증 데이터 분할 (80:20 비율)
        train_idx = int(len(df) * 0.8)
        train_df = df.iloc[:train_idx]
        val_df = df.iloc[train_idx:]
        
        # 사용할 피처 컬럼들 정의 (target_temp와 원본 Temperature는 보통 제외)
        # Preprocessing.py의 feature_selection 결과로 이미 피처들이 선택되었을 것.
        # 'ObservationTime', 'StationID' 등도 feature_selection에서 제거되었을 수 있으니,
        # 포함된 컬럼들을 기반으로 X를 구성해야 함.
        # 여기서 'Temperature'를 제외하는 것은, 'target_temp'를 예측하는데 현재 온도를 직접적인 feature로 쓰지 않겠다는 의미.
        # (이미 Preprocessing.py의 feature_selection에서 'Temperature'를 기준으로 피처를 골랐었음)
        
        # 사용 가능한 모든 컬럼에서 타겟 변수만 제외 (가장 일반적인 방법)
        # 또는 Preprocessing.py에서 선택된 피처 목록을 어떤 식으로든 전달받아 사용해야 함.
        # 지금은 'Temperature'도 제외하는 기존 로직을 따르되, errors='ignore' 추가
        
        # Preprocessing.py 에서 feature_selection 이 끝난 후의 컬럼들이 df에 들어있음.
        # 그 컬럼들 중에서 target_temp 와 Temperature 를 제외하고 X 로 사용.
        feature_columns = [col for col in df.columns if col not in ['target_temp', 'Temperature', 'ObservationTime', 'StationID']]
        # ObservationTime, StationID는 Preprocessing.py의 feature_selection에서 이미 제외되었을 가능성이 높음.
        # 명시적으로 제외하거나, 있는 컬럼만 사용하도록 방어적 코딩.
        
        # 실제 존재하는 컬럼만으로 X 구성
        X_cols_to_use = [col for col in feature_columns if col in df.columns]


        X_train = train_df[X_cols_to_use]
        y_train = train_df['target_temp']
        X_val = val_df[X_cols_to_use]
        y_val = val_df['target_temp']

        self.X_cols = X_train.columns.tolist() # evaluate_models에서 사용할 X 컬럼명 저장
        logging.info(f"Data loaded and split. X_train shape: {X_train.shape}, X_val shape: {X_val.shape}")
        logging.info(f"Features for training (X_cols): {self.X_cols}")
        
        return X_train, y_train, X_val, y_val
    

    def train_models(self) -> Dict[str, float]:
        X_train, y_train, X_val, y_val = self.load_data()
        training_times = {}
        model_scores = []
        total_models = len(self.models)
        trained_models = {}

        for idx, (name, model) in enumerate(self.models.items(), 1):
            print(f"Training model {idx}/{total_models}: {name}...")
            start_time = time.time()
            model.fit(X_train, y_train)
            training_time = time.time() - start_time
            training_times[name] = training_time
            # 검증 데이터로 RMSE 계산
            preds = model.predict(X_val)
            # rmse = mean_squared_error(y_val, preds) ** 0.5
            mse = mean_squared_error(y_val, preds)
            rmse = np.sqrt(mse)

            model_scores.append({'Model': name, 'RMSE': rmse, 'Training_Time': training_time, 'Model_Obj': model})
            print(f"{name} training completed in {training_time:.2f} seconds, RMSE: {rmse:.4f}")
            trained_models[name] = model

            # MLflow에 실험 기록
            with mlflow.start_run(run_name=name):
                mlflow.log_param("model_name", name)
                # 테스트용으로 주석 처리
                # mlflow.log_param("n_estimators", getattr(model, 'n_estimators', None) or getattr(model, 'max_iter', None))
                mlflow.log_metric("rmse", rmse)
                mlflow.log_metric("training_time", training_time)
                mlflow.sklearn.log_model(model, f"{name}_model")

        # RMSE 기준 상위 3개 모델만 선정
        model_scores = sorted(model_scores, key=lambda x: x['RMSE'])
        top_3 = model_scores[:3]
        for item in top_3:
            print(f"{item['Model']}")

        # self.training_times와 self.top_models 정보 저장
        self.training_times = {item['Model']: item['Training_Time'] for item in top_3}
        self.top_models = [item['Model'] for item in top_3]
        return self.training_times

    # 기존 국현님 코드
    # def evaluate_models(self) -> pd.DataFrame:
    #     _, _, X_val, y_val = self.load_data()
    #     print(f"[DEBUG] 평가 시 feature 목록: {self.X_cols}")
    #     X_val = X_val[self.X_cols]
    #     results = []
    #     # top_models만 평가
    #     models_to_eval = self.top_models if hasattr(self, 'top_models') else self.models.keys()
    #     total_models = len(models_to_eval)

    #     for idx, name in enumerate(models_to_eval, 1):
    #         print(f"{idx}/{total_models}: {name}...")
    #         # MLflow에서 모델 불러오기
    #         filter_str = f"tags.mlflow.runName = '{name}'"
    #         run_df = mlflow.search_runs(filter_string=filter_str, order_by=['metrics.rmse ASC'])
    #         run_id = run_df.iloc[0].run_id
    #         model_uri = f"runs:/{run_id}/{name}_model"
    #         model = mlflow.sklearn.load_model(model_uri)
    #         preds = model.predict(X_val)
    #         # rmse = mean_squared_error(y_val, preds, squared=False)
    #         mse = mean_squared_error(y_val, preds)
    #         rmse = np.sqrt(mse) 
            
    #         results.append({
    #             'Model': name,
    #             'RMSE': rmse,
    #             'Training_Time': self.training_times.get(name, 0)})

    # 수정한 evaluate_models 메소드
    def evaluate_models(self) -> pd.DataFrame:
        _, _, X_val, y_val = self.load_data() 

        # 혹시 self.X_cols가 None인 경우를 대비하여 예외 처리
        if self.X_cols is None:
            logging.error("self.X_cols is not set. Call train_models first or ensure X_cols is set in load_data.")
            raise ValueError("Feature column names (self.X_cols) not set.")

        # X_val에 self.X_cols에 없는 컬럼이 있을 경우를 대비하여, 있는 컬럼만 선택
        predict_X_val = X_val[[col for col in self.X_cols if col in X_val.columns]]

        results = []
        if not hasattr(self, 'top_models') or not self.top_models:
            logging.warning("No top_models found, evaluating all models defined in self.models or an empty set.")
            # self.top_models가 없으면, train_models에서 정의된 모든 모델을 평가하거나,
            # 아니면 아무것도 평가하지 않도록 처리해야 함. 여기서는 임시로 모든 모델을 대상으로 할 수 있지만,
            # 보통은 train_models에서 top_models를 결정하고 그걸 사용함.
            # 지금은 self.top_models가 train_models에서 잘 설정된다고 가정.
            if not hasattr(self, 'top_models'): # 아직 top_models가 없다면 빈 리스트로 초기화
                self.top_models = []


        models_to_eval = self.top_models # self.top_models가 train_models에서 설정됨
        total_models = len(models_to_eval)

        for idx, name in enumerate(models_to_eval, 1):
            print(f"Evaluating model {idx}/{total_models}: {name}...") # 평가 로그 추가
            filter_str = f"tags.mlflow.runName = '{name}'"
            run_df = mlflow.search_runs(filter_string=filter_str, order_by=['metrics.rmse ASC'])

            if run_df.empty:
                logging.warning(f"No runs found for model {name} with filter '{filter_str}'. Skipping evaluation.")
                continue # 해당 모델 실행 기록이 없으면 건너뛰기

            run_id = run_df.iloc[0].run_id
            model_uri = f"runs:/{run_id}/{name}_model"
            model = mlflow.sklearn.load_model(model_uri)

            preds = model.predict(predict_X_val) # predict_X_val 사용!

            # --- 여기가 핵심 수정 ---
            mse = mean_squared_error(y_val, preds)
            rmse = np.sqrt(mse) 
            # --- 여기까지 ---

            results.append({
                'Model': name,
                'RMSE': rmse,
                # self.training_times가 train_models에서 top_3 모델에 대해서만 설정되었을 수 있음
                'Training_Time': self.training_times.get(name, 0) 
            })

        results_df = pd.DataFrame(results)
        results_df = results_df.sort_values(by='RMSE')
        
        # Top 3 모델 선택
        top_3_models = results_df.head(3)
        print(top_3_models)
        
        # 평가 결과 저장
        results_df.to_csv('scripts/evaluation_results.csv', index=False)
        print(f"\n✅ Evaluation results saved to: scripts/evaluation_results.csv")
        return results_df

    def get_top_models(self, n: int = 3) -> List[str]:
        results_df = self.evaluate_models()
        return results_df.head(n)['Model'].tolist()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--data_path', type=str, default=None, help='학습에 사용할 데이터 파일 경로')
    args = parser.parse_args()

    # 데이터 경로 설정
    if args.data_path:
        data_path = args.data_path
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_path = os.path.join(base_dir, "data", "weather_data.csv")
    
    # 모델 학습 및 평가
    tree_models = Tree_Models(data_path)
    tree_models.training_times = tree_models.train_models()
    results = tree_models.evaluate_models()
    
    # Top 3 모델 출력
    top_models = tree_models.get_top_models(3)
    print("\nSelected Top 3 Models:")
    for i, model in enumerate(top_models, 1):
        print(f"{i}. {model}")
