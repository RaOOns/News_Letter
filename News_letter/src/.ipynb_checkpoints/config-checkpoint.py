import os
from dotenv import load_dotenv
load_dotenv()


def _int_env(name: str, default: int) -> int:
    v = (os.getenv(name) or "").strip()
    if not v:
        return default
    try:
        return int(v)
    except:
        return default

# 뉴스 섹션 (고정: 한국경제/세계경제/IT)
SECTIONS = ["한국 경제", "세계 경제", "IT"]

# src/config.py

NAVER_QUERIES = {
    "한국 경제": "한국 경제",
    "세계 경제": "세계 경제",
    "IT": "IT 인공지능",
}



# 각 섹션 메인 기사 수
HK_TOP_N = _int_env("HK_TOP_N", 3)
NAVER_TOP_N = _int_env("NAVER_TOP_N", 3)

# 네이버 검색 결과(관련기사) 최대 2개
RELATED_MAX = _int_env("RELATED_MAX", 2)

# 재시도 설정 (요청: 1분 간격 3번, 나중에 변경 가능)
RETRY_MAX_ATTEMPTS = _int_env("RETRY_MAX_ATTEMPTS", 3)
RETRY_INTERVAL_SEC = _int_env("RETRY_INTERVAL_SEC", 60)

# OpenAI
OPENAI_API_KEY = (os.getenv("OPENAI_API_KEY") or "").strip()
OPENAI_MODEL = (os.getenv("OPENAI_MODEL") or "gpt-4.1-mini").strip()

# NAVER OpenAPI
NAVER_CLIENT_ID = (os.getenv("NAVER_CLIENT_ID") or "").strip()
NAVER_CLIENT_SECRET = (os.getenv("NAVER_CLIENT_SECRET") or "").strip()

# 메일 수신자: 쉼표로 확장 가능
RECIPIENTS = [x.strip() for x in (os.getenv("RECIPIENTS") or "").split(",") if x.strip()]

# Outlook SMTP(테넌트 정책에 따라 SMTP AUTH가 막힐 수 있음)
SMTP_HOST = (os.getenv("SMTP_HOST") or "smtp.office365.com").strip()
SMTP_PORT = _int_env("SMTP_PORT", 587)
SMTP_USER = (os.getenv("SMTP_USER") or "").strip()
SMTP_PASS = (os.getenv("SMTP_PASS") or "").strip()

# 제목 포맷 (요청 반영)
MAIL_SUBJECT_FMT = "[DH 뉴스레터] {date} 주요 이슈 요약 (한국경제 RSS + 네이버 뉴스)"
BLOG_TITLE_FMT = "[뉴스레터] {date} 주요 이슈 요약 (한국경제 RSS + 네이버 뉴스)"

# 상단 문구 (A안 + 네이버 추가 + 3개 분야 문구)
TOP_NOTE = (
    '<div style="line-height:1.3; font-size:12px; color:#666;">'
    '※ 본 내용은 "한국경제"신문의 RSS 기사 및 네이버 뉴스 검색 결과를 토대로 제작하였습니다.<br>'
    '※ 한국경제, 세계 경제, IT 분야의 데일리 주요 뉴스를 요약합니다.'
    '</div>'
)

# state db
STATE_DB_PATH = os.path.join("data", "state.db")
