import requests
import schedule
import time
import os
import json
from datetime import datetime, timezone, timedelta, date

# 환경변수
FRED_API_KEY = os.getenv('FRED_API_KEY')
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# 한국 시간대
KST = timezone(timedelta(hours=9))

# 주요 경제지표 정의
ECONOMIC_INDICATORS = {
    'UNRATE': {
        'name': '실업률',
        'unit': '%',
        'importance': 'critical',
        'description': '미국 실업률'
    },
    'CPIAUCSL': {
        'name': 'CPI (소비자물가지수)',
        'unit': '%',
        'importance': 'critical',
        'description': '전년동월대비 인플레이션율'
    },
    'PAYEMS': {
        'name': '비농업 취업자 수',
        'unit': '천명',
        'importance': 'critical',
        'description': '월간 고용 증가'
    },
    'GDPC1': {
        'name': 'GDP',
        'unit': '%',
        'importance': 'important',
        'description': '분기별 경제성장률'
    },
    'RRSFS': {
        'name': '소매판매',
        'unit': '%',
        'importance': 'important',
        'description': '월간 소매판매 증감률'
    }
}

def get_korean_time():
    """현재 한국 시간 반환"""
    return datetime.now(KST)

def is_business_day():
    """평일인지 확인 (월-금)"""
    korean_time = get_korean_time()
    weekday = korean_time.weekday()
    return weekday < 5

def should_send_briefing():
    """브리핑을 보내야 하는 시간인지 확인"""
    if not is_business_day():
        print("📅 주말이므로 브리핑을 건너뜁니다.")
        return False
    
    korean_time = get_korean_time()
    hour = korean_time.hour
    minute = korean_time.minute
    
    # 오전 7시 30분에만 전송
    if hour == 7 and minute == 30:
        return True
    
    return False

def get_fred_data(series_id, limit=10):
    """FRED API에서 경제지표 데이터 가져오기"""
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        'series_id': series_id,
        'api_key': FRED_API_KEY,
        'file_type': 'json',
        'limit': limit,
        'sort_order': 'desc'  # 최신 데이터부터
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        if response.status_code == 200:
            data = response.json()
            return data.get('observations', [])
        else:
            print(f"❌ FRED API 오류 ({series_id}): {response.status_code}")
            return []
    except Exception as e:
        print(f"🚨 FRED API 예외 ({series_id}): {e}")
        return []

def get_latest_indicators():
    """최신 경제지표 데이터 수집"""
    indicators_data = {}
    
    for series_id, info in ECONOMIC_INDICATORS.items():
        print(f"📊 {info['name']} 데이터 수집 중...")
        
        observations = get_fred_data(series_id)
        if observations:
            latest = observations[0]
            previous = observations[1] if len(observations) > 1 else None
            
            indicators_data[series_id] = {
                'info': info,
                'latest_value': latest.get('value'),
                'latest_date': latest.get('date'),
                'previous_value': previous.get('value') if previous else None,
                'previous_date': previous.get('date') if previous else None
            }
    
    return indicators_data

def calculate_change(current, previous):
    """변화율 계산"""
    if not current or not previous or current == '.' or previous == '.':
        return None
    
    try:
        current_val = float(current)
        previous_val = float(previous)
        change = current_val - previous_val
        return change
    except (ValueError, TypeError):
        return None

def format_change(change):
    """변화를 이모지와 함께 포맷"""
    if change is None:
        return "📊 N/A"
    elif change > 0:
        return f"📈 +{change:.2f}"
    elif change < 0:
        return f"📉 {change:.2f}"
    else:
        return f"➡️ {change:.2f}"

def format_economic_briefing(indicators_data):
    """경제지표 브리핑 메시지 포맷"""
    korean_time = get_korean_time()
    
    # 중요도별 정렬
    critical_indicators = []
    important_indicators = []
    
    for series_id, data in indicators_data.items():
        if data['info']['importance'] == 'critical':
            critical_indicators.append((series_id, data))
        elif data['info']['importance'] == 'important':
            important_indicators.append((series_id, data))
    
    # 메시지 구성
    message = f"""🇺🇸 <b>미국 경제지표 브리핑</b>
📅 {korean_time.strftime('%Y년 %m월 %d일')} 발송

<b>📊 주요 지표:</b>"""
    
    # 중요 지표들
    for series_id, data in critical_indicators:
        info = data['info']
        current = data['latest_value']
        previous = data['previous_value']
        latest_date = data['latest_date']
        
        if current and current != '.':
            change = calculate_change(current, previous)
            change_str = format_change(change)
            
            message += f"""
- <b>{info['name']}</b>: {current}{info['unit']} {change_str}"""
            
            if latest_date:
                # 날짜 포맷팅 (2024-08-01 형태)
                try:
                    date_obj = datetime.strptime(latest_date, '%Y-%m-%d')
                    formatted_date = date_obj.strftime('%m/%d')
                    message += f" ({formatted_date})"
                except:
                    pass
    
    # 일반 지표들
    if important_indicators:
        message += f"""

<b>📈 기타 지표:</b>"""
        
        for series_id, data in important_indicators:
            info = data['info']
            current = data['latest_value']
            previous = data['previous_value']
            
            if current and current != '.':
                change = calculate_change(current, previous)
                change_str = format_change(change)
                
                message += f"""
- {info['name']}: {current}{info['unit']} {change_str}"""
    
    # 시장 전망 (간단한 로직)
    message += f"""

<b>📊 브리핑 요약:</b>
최신 미국 경제지표를 확인하세요.

⏰ {korean_time.strftime('%H:%M')} (KST) 발송
🔄 다음 브리핑: 내일 오전 7:30"""
    
    return message

def send_telegram_message(message):
    """텔레그램으로 메시지 전송"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    
    try:
        response = requests.post(url, data=data, timeout=30)
        if response.status_code == 200:
            print("✅ 텔레그램 브리핑 전송 성공")
            return True
        else:
            print(f"❌ 텔레그램 전송 실패: {response.text}")
            return False
    except Exception as e:
        print(f"🚨 텔레그램 오류: {e}")
        return False

def send_economic_briefing():
    """경제지표 브리핑 전송"""
    korean_time = get_korean_time()
    
    if not should_send_briefing():
        return
    
    print(f"📊 경제지표 브리핑 준비 중... {korean_time.strftime('%H:%M:%S')}")
    
    # 경제지표 데이터 수집
    indicators_data = get_latest_indicators()
    
    if not indicators_data:
        print("❌ 경제지표 데이터를 가져올 수 없습니다.")
        return
    
    # 브리핑 메시지 생성
    briefing_message = format_economic_briefing(indicators_data)
    
    # 텔레그램 전송
    success = send_telegram_message(briefing_message)
    
    if success:
        print("✅ 경제지표 브리핑 전송 완료")
    else:
        print("❌ 브리핑 전송 실패")

def send_startup_message():
    """봇 시작 알림"""
    korean_time = get_korean_time()
    weekday_name = ['월', '화', '수', '목', '금', '토', '일'][korean_time.weekday()]
    
    startup_message = f"""🇺🇸 <b>미국 경제지표 브리핑 봇 시작!</b>

📅 {korean_time.strftime('%Y-%m-%d')} ({weekday_name}요일)
⏰ {korean_time.strftime('%H:%M:%S')} (KST)

<b>📊 브리핑 스케줄:</b>
- 매일 오전 7:30 정기 발송
- 주요 경제지표 자동 수집
- 평일만 운영 (주말 휴무)

<b>📈 포함 지표:</b>
- 실업률, CPI, 비농업취업자수
- GDP, 소매판매 등

다음 브리핑: 내일 오전 7:30 📅"""

    send_telegram_message(startup_message)

# 스케줄 설정: 매일 오전 7:30
schedule.every().day.at("07:30").do(send_economic_briefing)

# 테스트용: 매시간 정각에도 실행 (나중에 제거)
schedule.every().hour.at(":00").do(send_economic_briefing)

print("🇺🇸 미국 경제지표 브리핑 봇이 시작되었습니다!")
print(f"📊 FRED_API_KEY: {'✅ 설정됨' if FRED_API_KEY else '❌ 미설정'}")
print(f"📱 BOT_TOKEN: {'✅ 설정됨' if BOT_TOKEN else '❌ 미설정'}")
print(f"💬 CHAT_ID: {'✅ 설정됨' if CHAT_ID else '❌ 미설정'}")

korean_time = get_korean_time()
print(f"🕐 현재 한국 시간: {korean_time.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"📅 평일 여부: {'✅ 평일' if is_business_day() else '❌ 주말'}")

# 시작 알림 및 테스트
if FRED_API_KEY and BOT_TOKEN and CHAT_ID:
    send_startup_message()
    
    # 즉시 테스트 브리핑 전송
    print("🚀 테스트 브리핑을 전송합니다...")
    send_economic_briefing()
else:
    print("⚠️ 환경변수가 설정되지 않았습니다!")

# 스케줄러 실행
print("⏰ 스케줄러 시작... (매일 오전 7:30 브리핑)")
while True:
    schedule.run_pending()
    time.sleep(60)
