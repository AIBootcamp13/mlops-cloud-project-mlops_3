import os

# API 관련 상수
KMA_STATION_ID = 108
KMA_API_URL = 'https://apihub.kma.go.kr/api/typ01/url/kma_sfctm3.php'

# 데이터 처리 관련 상수
LOOKBACK_DAYS = 30  # 피처 생성 시 참조할 과거 데이터 기간

# 날씨 데이터 컬럼
WEATHER_COLUMNS = [
    "ObservationTime", "StationID", "WindDirection",
    "WindSpeed", "GustDirection", "GustSpeed", "GustTime",
    "LocalPressure", "SeaLevelPressure", "PressureTrend",
    "PressureChange", "Temperature", "DewPointTemperature",
    "RelativeHumidity", "VaporPressure",
    "HourlyRainfall", "DailyRainfall", "CumulativeRainfall",
    "RainfallIntensity", "SnowDepth3Hr",
    "DailySnowDepth", "TotalSnowDepth", "CurrentWeatherCode",
    "PastWeatherCode", "WeatherCode",
    "TotalCloudCover", "MidLowCloudCover", "LowestCloudHeight",
    "CloudType", "UpperCloudType",
    "MidCloudType", "LowCloudType", "Visibility", "SunshineDuration",
    "SolarRadiation", "GroundCondition",
    "GroundTemperature", "SoilTemperature5cm",
    "SoilTemperature10cm", "SoilTemperature20cm",
    "SoilTemperature30cm",
    "SeaCondition", "WaveHeight", "MaxWindForce",
    "PrecipitationData", "ObservationType"
]

WEATHER_KOREAN_COLUMNS = [
    "관측시각", "지점번호", "풍향",
    "풍속", "돌풍방향", "돌풍속도",
    "돌풍시각", "현지기압", "해면기압", "기압경향",
    "기압변화량", "기온", "이슬점온도",
    "상대습도", "수증기압", "시간강수량",
    "일강수량", "누적강수량", "강수강도", "3시간적설",
    "일적설", "총적설", "현재날씨코드",
    "과거날씨코드", "일기코드", "전운량",
    "중하층운량", "최저운고", "운형", "상층운형",
    "중층운형", "하층운형", "시정", "일조시간",
    "일사량", "지면상태", "지면온도",
    "5cm지중온도", "10cm지중온도", "20cm지중온도", "30cm지중온도",
    "해면상태", "파고", "최대풍력", "강수자료", "관측유형"
]
