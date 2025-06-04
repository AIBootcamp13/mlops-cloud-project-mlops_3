# 기상청 API 텍스트 데이터를 pandas.read_fwf()로 파싱 성공!
# TODO : 이제 이걸 활용해서 날씨 데이터를 S3에 저장하는 작업하기

import requests
import pandas as pd
from io import StringIO
from datetime import datetime
from dotenv import load_dotenv
import os

# .env에서 AUTH_KEY 불러오기
load_dotenv()
AUTH_KEY = os.getenv("AUTH_KEY")

# 기상청 API URL 설정
KMA_API_URL = "https://apihub.kma.go.kr/api/typ01/url/kma_sfctm3.php"
params = {
    "authKey": AUTH_KEY,
    "pageNo": 1,
    "numOfRows": 10,
    "dataType": "JSON",  # 의미 없음. 실제는 텍스트 고정폭
    "stnIds": 159  # 기상 관측소 ID 예시
}

# API 요청
response = requests.get(KMA_API_URL, params=params)
print("응답 상태 코드:", response.status_code)

# 응답 내용
raw_text = response.text

# 고정폭 데이터만 추출 (주석 줄 제거)
data_lines = [line for line in raw_text.splitlines() if not line.startswith("#") and line.strip()]
raw_data_str = "\n".join(data_lines)

# 문자열을 파일처럼 다루기
data_io = StringIO(raw_data_str)

# 고정폭 텍스트의 폭 수동 지정 (공식 문서가 없으므로 예시 기준)
column_widths = [10, 5, 4, 5, 5, 5, 8, 8, 8, 5, 6, 6, 6, 6, 6, 8]  # 필요 컬럼만 예시로

# 열 이름 설정 (예: 날짜, 기온, 습도 등)
column_names = ["dt", "stn", "wd", "ws", "gst1", "gst2", "pa", "ps", "pt", "pr", "ta", "td", "hm", "pv", "rn", "extra"]

# DataFrame으로 읽기
df = pd.read_fwf(data_io, widths=column_widths, names=column_names)

# 출력
print(df.head())