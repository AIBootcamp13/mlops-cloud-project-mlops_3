FROM python:3.9-slim

WORKDIR /mlops_team

COPY requirements.txt /mlops_team/requirements.txt

RUN apt-get update && apt-get install -y libgomp1
RUN pip install --no-cache-dir -r /mlops_team/requirements.txt

COPY . /mlops_team/

# fastapi 기본 포트
EXPOSE 8000 

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]