# 옷추천 로직
# TODO: 지금은 기온만 고려하는데, 나중에 추가적으로 습도, 바람, 비, 눈오는지 등을 고려할 수 있음

# def get_recommendation_by_predicted_temp(temp: float) -> str:
#     if temp >= 25:
#         return f"예상 기온({temp:.1f}°C): 반팔과 시원한 옷차림 추천합니다! ☀️"
#     elif 20 <= temp < 25:
#         return f"예상 기온({temp:.1f}°C): 얇은 긴팔이나 반팔에 가벼운 겉옷이 좋겠어요. 😄"
#     elif 15 <= temp < 20:
#         return f"예상 기온({temp:.1f}°C): 긴팔과 가디건이나 자켓을 준비하세요. 🧥"
#     elif 10 <= temp < 15:
#         return f"예상 기온({temp:.1f}°C): 따뜻한 스웨터나 경량 패딩이 필요할 수 있어요. 🌬️"
#     else: # 10도 미만
#         return f"예상 기온({temp:.1f}°C): 추워요! 두꺼운 외투와 따뜻한 옷차림은 필수! 🥶"



"""
옷추천 로직 수정
민감도에 따라 체감 온도 보정값 설정
추위를 많이 타면 체감 온도를 2도 낮게
더위를 많이 타면 체감 온도를 2도 높게
보통은 체감 온도를 변경하지 않음
체감 온도에 따라 옷추천 로직 수정
"""

def get_cloth_sense(temp: float, sensitivity: str = "normal") -> str:
    """
    temp: 예측된 기온 (float)
    sensitivity: 'cold' (추위를 많이 탐), 'normal' (보통), 'hot' (더위를 많이 탐)
    """
    # 민감도에 따라 체감 온도 보정값 설정
    if sensitivity == "cold":
        adj_temp = temp - 2  # 추위를 많이 타면 체감 온도를 2도 낮게
    elif sensitivity == "hot":
        adj_temp = temp + 2  # 더위를 많이 타면 체감 온도를 2도 높게
    else:
        adj_temp = temp

    if adj_temp >= 25:
        return f"예상 기온({temp:.1f}°C, 민감도 반영:{adj_temp:.1f}°C): 반팔과 시원한 옷차림 추천! ☀️"
    elif 20 <= adj_temp < 25:
        return f"예상 기온({temp:.1f}°C, 민감도 반영:{adj_temp:.1f}°C): 얇은 긴팔/반팔+가벼운 겉옷 추천 😄"
    elif 15 <= adj_temp < 20:
        return f"예상 기온({temp:.1f}°C, 민감도 반영:{adj_temp:.1f}°C): 긴팔+가디건/자켓 추천 🧥"
    elif 10 <= adj_temp < 15:
        return f"예상 기온({temp:.1f}°C, 민감도 반영:{adj_temp:.1f}°C): 스웨터/경량 패딩 추천 🌬️"
    else:
        return f"예상 기온({temp:.1f}°C, 민감도 반영:{adj_temp:.1f}°C): 두꺼운 외투와 따뜻한 옷차림 필수! 🥶"