from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.wearher.v1_0_0.preprocess import WeatherPreprocess
from data.wearher.v1_0_0.ingest_raw_wearher import collect_weather_data_with_time
from scripts.pipeline import main as run_model_train

def get_execution_time(**context):
    """실행 시간을 가져오는 함수"""
    execution_date = context['execution_date']
    return execution_date.strftime('%Y%m%d%H%M')

def run_weather_preprocessing():
    WeatherPreprocess()
    return None

default_args = {
    'owner': 'airflow',
    'retries': 1,
    'retry_delay': timedelta(minutes=3),
}

dag = DAG(
    dag_id='wearher_data_pipeline',
    default_args=default_args,
    description='등록 후 최초 1회 실행 + 이후 매일 새벽 2시 자동 실행',
    schedule_interval='0 2 * * *',  # 매일 새벽 2시
    start_date=days_ago(0),
    catchup=False,
    max_active_runs=1,
    tags=['weather', 'mlops'],
)


# Task 1: 날씨 데이터 수집
collect_weather_data = PythonOperator(
    task_id='collect_weather_data',
    python_callable=collect_weather_data_with_time,
    provide_context=True,  # 컨텍스트 정보 전달
    dag=dag,
)

# Task 3: 데이터 전처리
preprocess_data = PythonOperator(
    task_id='preprocess_weather_data',
    python_callable=run_weather_preprocessing,
    provide_context=True,
    dag=dag,
)

model_train = PythonOperator(
    task_id='model_train',
    python_callable=run_model_train,
    provide_context=True,
    op_kwargs={
        'start_year': 2024,
        'epochs':2,
    },
    dag=dag,
)

# Task 의존성 정의
collect_weather_data >> preprocess_data >> model_train
