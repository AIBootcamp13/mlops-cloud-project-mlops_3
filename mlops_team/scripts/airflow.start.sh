#!/bin/bash
airflow db init
airflow users create \
    --username admin \
    --firstname admin \
    --lastname lee \
    --role Admin \
    --email admin@airflow.com \
    --password admin123
# airflow webserver -p 8181 & airflow scheduler


# 스케쥴러는 먼저 백그라운드 실행
airflow scheduler &

# 이후에 webserver는 포그라운드로 (컨테이너 유지 목적)
exec airflow webserver -p 8181