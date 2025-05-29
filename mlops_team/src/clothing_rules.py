# 옷추천 로직
# TODO: 지금은 기온만 고려하는데, 나중에 추가적으로 습도, 바람, 비, 눈오는지 등을 고려할 수 있음

def get_recommendation_by_predicted_temp(temp: float) -> str:
    if temp >= 25:
        return f"예상 기온({temp:.1f}°C): 반팔과 시원한 옷차림 추천합니다! ☀️"
    elif 20 <= temp < 25:
        return f"예상 기온({temp:.1f}°C): 얇은 긴팔이나 반팔에 가벼운 겉옷이 좋겠어요. 😄"
    elif 15 <= temp < 20:
        return f"예상 기온({temp:.1f}°C): 긴팔과 가디건이나 자켓을 준비하세요. 🧥"
    elif 10 <= temp < 15:
        return f"예상 기온({temp:.1f}°C): 따뜻한 스웨터나 경량 패딩이 필요할 수 있어요. 🌬️"
    else: # 10도 미만
        return f"예상 기온({temp:.1f}°C): 추워요! 두꺼운 외투와 따뜻한 옷차림은 필수! 🥶"