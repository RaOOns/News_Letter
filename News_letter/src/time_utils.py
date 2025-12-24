from datetime import datetime, timedelta
import pytz

KST = pytz.timezone("Asia/Seoul")

def now_kst() -> datetime:
    return datetime.now(KST)

def fmt_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M")

def fmt_date(dt: datetime) -> str:
    return dt.strftime("%Y년 %m월 %d일")

def run_date_str(now: datetime) -> str:
    return now.strftime("%Y-%m-%d")

def last_24h_window_from_now(now: datetime):
    end = now
    start = now - timedelta(hours=24)
    return start, end
