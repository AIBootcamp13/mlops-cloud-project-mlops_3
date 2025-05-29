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


class Tree_Models:
    def __init__(self, data_path: str, experiment_name: str = "weather_regression"):
        self.data_path = data_path
        self.experiment_name = experiment_name
        mlflow.set_experiment(self.experiment_name)
        # 트리 모델 정의
        self.models = {
            'LightGBM': LGBMRegressor(n_estimators=100, learning_rate=0.1),
            'XGBoost': XGBRegressor(n_estimators=100, learning_rate=0.1, verbosity=0),
            'CatBoost': CatBoostRegressor(n_estimators=100, learning_rate=0.1, verbose=0),
            'RandomForest': RandomForestRegressor(n_estimators=100),
            'GradientBoosting': GradientBoostingRegressor(n_estimators=100, learning_rate=0.1),
            'ExtraTrees': ExtraTreesRegressor(n_estimators=100),
            'HistGradientBoosting': HistGradientBoostingRegressor(max_iter=100, learning_rate=0.1)}


    def load_data(self) -> Tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series]:
        df = pd.read_csv(self.data_path)
        df = df.sort_values(by='측정시간')  # 시계열 순서 유지
        split_index = int(len(df) * 0.8)

        train_df = df.iloc[:split_index]
        val_df = df.iloc[split_index:]

        X_train = train_df[['현재기온', '현재습도', '현재풍속', '시각']]
        y_train = train_df['1시간뒤기온']
        X_val = val_df[['현재기온', '현재습도', '현재풍속', '시각']]
        y_val = val_df['1시간뒤기온']
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
            rmse = mean_squared_error(y_val, preds, squared=False)
            model_scores.append({'Model': name, 'RMSE': rmse, 'Training_Time': training_time, 'Model_Obj': model})
            print(f"{name} training completed in {training_time:.2f} seconds, RMSE: {rmse:.4f}")
            trained_models[name] = model

            # === MLflow에 실험 기록 ===
            with mlflow.start_run(run_name=name):
                mlflow.log_param("model_name", name)
                mlflow.log_param("n_estimators", getattr(model, 'n_estimators', None) or getattr(model, 'max_iter', None))
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


    def evaluate_models(self) -> pd.DataFrame:
        _, _, X_val, y_val = self.load_data()
        results = []
        # top_models만 평가
        models_to_eval = self.top_models if hasattr(self, 'top_models') else self.models.keys()
        total_models = len(models_to_eval)

        for idx, name in enumerate(models_to_eval, 1):
            print(f"{idx}/{total_models}: {name}...")
            # MLflow에서 모델 불러오기
            model_uri = f"runs:/{mlflow.search_runs(filter_string=f'tags.mlflow.runName = \"{name}\"', order_by=['metrics.rmse ASC']).iloc[0].run_id}/{name}_model"
            model = mlflow.sklearn.load_model(model_uri)
            preds = model.predict(X_val)
            rmse = mean_squared_error(y_val, preds, squared=False)
            results.append({
                'Model': name,
                'RMSE': rmse,
                'Training_Time': self.training_times.get(name, 0)})

        results_df = pd.DataFrame(results)
        results_df = results_df.sort_values(by='RMSE')
        
        # Top 3 모델 선택
        top_3_models = results_df.head(3)
        print(top_3_models)
        
        # 평가 결과 저장
        results_df.to_csv('evaluation_results.csv', index=False)
        print(f"\n✅ Evaluation results saved to: evaluation_results.csv")
        return results_df

    def get_top_models(self, n: int = 3) -> List[str]:
        results_df = self.evaluate_models()
        return results_df.head(n)['Model'].tolist()


if __name__ == "__main__":
    # 데이터 경로 설정
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
