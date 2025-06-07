#!/bin/bash
airflow db init
airflow users create \
    --username admin \
    --firstname admin \
    --lastname lee \
    --role Admin \
    --email admin@airflow.com \
    --password admin123
airflow webserver -p 8181 & airflow scheduler