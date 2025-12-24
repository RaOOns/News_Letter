from __future__ import annotations
import os
import time
import socket
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, Page  # ✅ Page 추가


def _env_required(key: str) -> str:
    v = os.getenv(key)
    if not v:
        raise RuntimeError(f"환경변수 {key} 가 비어있습니다. .env 를 확인하세요.")
    return v.strip()


def _find_chrome_exe() -> str:
    candidates = [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    raise RuntimeError("Chrome 실행 파일을 찾지 못했습니다. Chrome이 설치되어 있는지 확인하세요.")


def _wait_port_open(host: str, port: int, timeout_sec: int = 10) -> None:
    end = time.time() + timeout_sec
    while time.time() < end:
        try:
            with socket.create_connection((host, port), timeout=1):
                return
        except OSError:
            time.sleep(0.2)
    raise RuntimeError(f"remote debugging 포트({port})가 열리지 않았습니다.")


def _click_first_visible(page: Page, selectors: list[str], timeout_ms: int = 1500) -> bool:
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0 and loc.is_visible():
                loc.click(timeout=timeout_ms)
                return True
        except Exception:
            continue
    return False


def _fill_first_visible(page: Page, selectors: list[str], value: str, timeout_ms: int = 1500) -> bool:
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0 and loc.is_visible():
                loc.fill(value, timeout=timeout_ms)
                return True
        except Exception:
            continue
    return False


def _kakao_login_auto(page: Page, kakao_id: str, kakao_pw: str) -> None:
    page.wait_for_load_state("domcontentloaded", timeout=20000)
    page.wait_for_timeout(800)

    _click_first_visible(page, [
        "text=카카오계정",
        "text=카카오계정으로 로그인",
        "text=계정 로그인",
        "a:has-text('카카오계정')",
        "button:has-text('카카오계정')",
    ], timeout_ms=2000)

    page.wait_for_timeout(700)

    id_selectors = [
        "input#loginId",
        "input[name='loginId']",
        "input[name='email']",
        "input[type='email']",
        "input[placeholder*='이메일']",
        "input[placeholder*='카카오메일']",
        "input[aria-label*='아이디']",
        "input[aria-label*='이메일']",
        "input[id*='email']",
        "input[id*='id']",
    ]
    pw_selectors = [
        "input#password",
        "input[name='password']",
        "input[type='password']",
        "input[placeholder*='비밀번호']",
        "input[aria-label*='비밀번호']",
    ]
    login_btn_selectors = [
        "button[type='submit']",
        "button:has-text('로그인')",
        "button:has-text('Log in')",
        "button:has-text('다음')",
        "button:has-text('확인')",
        "input[type='submit']",
    ]

    if not _fill_first_visible(page, id_selectors, kakao_id, timeout_ms=4000):
        raise RuntimeError("카카오 ID 입력칸을 찾지 못했습니다. (구조 변경 가능)")
    page.wait_for_timeout(250)

    if not _fill_first_visible(page, pw_selectors, kakao_pw, timeout_ms=4000):
        raise RuntimeError("카카오 PW 입력칸을 찾지 못했습니다. (구조 변경 가능)")
    page.wait_for_timeout(250)

    if not _click_first_visible(page, login_btn_selectors, timeout_ms=4000):
        try:
            page.keyboard.press("Enter")
        except Exception:
            raise RuntimeError("카카오 로그인 버튼을 찾지 못했습니다. (구조 변경 가능)")

    page.wait_for_load_state("domcontentloaded", timeout=20000)
    page.wait_for_timeout(800)


def _wait_for_2fa_and_click_continue(page: Page, max_wait_sec: int = 300) -> None:
    deadline = time.time() + max_wait_sec
    continue_candidates = [
        "button:has-text('계속하기')",
        "button:has-text('계속')",
        "button:has-text('확인')",
        "button:has-text('다음')",
        "a:has-text('계속하기')",
        "a:has-text('계속')",
        "text=계속하기",
        "text=계속",
        "text=확인",
    ]

    while time.time() < deadline:
        if "tistory.com" in page.url and "kakao.com" not in page.url:
            return

        if _click_first_visible(page, continue_candidates, timeout_ms=2500):
            page.wait_for_timeout(800)
            if "tistory.com" in page.url and "kakao.com" not in page.url:
                return

        page.wait_for_timeout(600)

    raise RuntimeError(f"2단계 인증 대기 시간 초과({max_wait_sec}s).")


def _pick_free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def main():
    # ✅ 실행 위치가 바뀌어도 src import 깨지지 않게 project root를 sys.path에 추가
    project_root = Path(__file__).resolve().parent.parent  # .../New_letter
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from src.logger_utils import setup_logger  # ✅ 여기로 수정
    logger = setup_logger()

    load_dotenv()

    blog_name = _env_required("TISTORY_BLOG_NAME")
    kakao_id = _env_required("KAKAO_ID")
    kakao_pw = _env_required("KAKAO_PW")

    user_data_dir = os.path.abspath("chrome_profile")
    port = _pick_free_port()
    chrome_exe = _find_chrome_exe()

    # ✅ (중요) 크롬은 딱 1번만 실행
    cmd = [
        chrome_exe,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data_dir}",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    logger.info(f"[CHROME] launched: port={port}, profile={user_data_dir}")

    # ✅ 포트 열릴 때까지 대기 (이게 실패하면 바로 원인 출력됨)
    _wait_port_open("127.0.0.1", port, timeout_sec=30)
    logger.info("[CHROME] remote debugging port is open")

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = context.new_page()

        page.goto(f"https://{blog_name}.tistory.com/manage", wait_until="domcontentloaded")
        page.wait_for_timeout(1200)

        _click_first_visible(page, [
            "a:has-text('카카오계정')",
            "button:has-text('카카오계정')",
            "text=카카오계정",
            "a:has-text('로그인')",
            "button:has-text('로그인')",
            "text=로그인",
        ], timeout_ms=2500)

        if "kakao.com" in page.url:
            logger.info("[KAKAO] login page detected → auto fill")
            _kakao_login_auto(page, kakao_id, kakao_pw)

            logger.info("[KAKAO] waiting 2FA + auto continue")
            _wait_for_2fa_and_click_continue(page, max_wait_sec=300)

        if "tistory.com" in page.url and "kakao.com" not in page.url:
            logger.info("[TISTORY] login success")
            print("[OK] 티스토리 로그인 완료")
        else:
            logger.warning(f"[TISTORY] login uncertain. url={page.url}")
            print("[Warning] 로그인 상태 불확실, 현재 URL:", page.url)

        print("[Done] 코드 종료합니다. (크롬은 외부 프로세스라 창은 그대로 남습니다)")
        return


if __name__ == "__main__":
    main()
