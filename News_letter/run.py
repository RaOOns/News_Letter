import time
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional
import subprocess


from src.logger_utils import setup_logger
from src.time_utils import now_kst, fmt_dt, fmt_date, run_date_str, last_24h_window_from_now
from src.state_store import StateStore
from src.config import (
    SECTIONS, HK_TOP_N, NAVER_TOP_N,
    RETRY_MAX_ATTEMPTS, RETRY_INTERVAL_SEC,
    NAVER_CLIENT_ID, NAVER_CLIENT_SECRET,
    RECIPIENTS,
    MAIL_SUBJECT_FMT, BLOG_TITLE_FMT, TOP_NOTE,
    STATE_DB_PATH,
)
from src.hankyung_rss import fetch_hankyung_rss, HKItem
from src.naver_search_api import NaverNewsSearchAPI, NaverNewsItem
from src.article_fetcher import fetch_article_text
from src.gpt_rewriter_grounded import rewrite_article_grounded
from src.html_renderer import RenderItem, render_newsletter_html
from src.outlook_app_mailer import send_mail_via_outlook_app
from src.config import NAVER_QUERIES


def _within_window(dt, start, end) -> bool:
    if not dt:
        return False
    return start <= dt <= end


def _select_latest(items: List[HKItem], start, end, n: int) -> List[HKItem]:
    filtered = [x for x in items if _within_window(x.published_kst, start, end)]
    filtered.sort(key=lambda x: x.published_kst or 0, reverse=True)
    return filtered[:n]


def _normalize_title(s: str) -> str:
    s = (s or "").lower()
    for ch in ["[", "]", "(", ")", "…", "\"", "'", "’", "“", "”", "·", "|"]:
        s = s.replace(ch, " ")
    s = " ".join(s.split())
    return s.strip()


def _jaccard(a: str, b: str) -> float:
    sa = set(_normalize_title(a).split())
    sb = set(_normalize_title(b).split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _log_top_titles(logger, tag: str, sec: str, items, limit: int = 3):
    for it in items[:limit]:
        dt = getattr(it, "published_kst", None) or getattr(it, "pubdate_kst", None)
        dt_s = fmt_dt(dt) if dt else "NO_DATE"
        title = getattr(it, "title", "")
        link = getattr(it, "link", "")
        logger.info(f"[{tag}] {sec} - {title} / {dt_s} / {link}")


def _open_file_default_app(path: Path, logger) -> None:
    """
    Windows 기본 앱으로 파일 열기 (txt)
    """
    try:
        if not path.exists():
            logger.warning(f"[OPEN] file not found: {path}")
            return
        # Windows: start "" "file"
        subprocess.Popen(["cmd", "/c", "start", "", str(path)], shell=False)
        logger.info(f"[OPEN] opened file: {path}")
    except Exception as e:
        logger.warning(f"[OPEN] failed to open file: {path} err={e}")


def _launch_tistory_login_only(logger, script_path: str = "src/tistory_login_only.py") -> None:
    """
    tistory_login_only.py를 별도 프로세스로 실행 (run.py는 기다리지 않고 종료 가능)
    """
    p = Path(script_path)
    if not p.exists():
        logger.warning(f"[TISTORY] login script not found: {p}")
        return

    try:
        cmd = [sys.executable, str(p)]
        subprocess.Popen(cmd, cwd=str(Path.cwd()), close_fds=True)
        logger.info(f"[TISTORY] launched: {' '.join(cmd)}")
    except Exception as e:
        logger.warning(f"[TISTORY] failed to launch login script: {e}")


def main():
    print("RUN.PY STARTED")
    logger = setup_logger()
    now = now_kst()
    run_date = run_date_str(now)
    w_start, w_end = last_24h_window_from_now(now)

    recipients = list(RECIPIENTS or [])

    logger.info(f"[{run_date}] News_letter started.")
    logger.info(f"Recipients count: {len(recipients)}")
    logger.info(f"Now (KST): {fmt_dt(now)}")
    logger.info(f"News window (24h): {fmt_dt(w_start)} ~ {fmt_dt(w_end)}")

    store = StateStore(STATE_DB_PATH)
    if store.is_success(run_date):
        logger.info(f"[{run_date}] Already SUCCESS. Exit without doing anything.")
        return

    naver_api: Optional[NaverNewsSearchAPI] = None
    if NAVER_CLIENT_ID and NAVER_CLIENT_SECRET:
        naver_api = NaverNewsSearchAPI(NAVER_CLIENT_ID, NAVER_CLIENT_SECRET)
        logger.info("[NAVER] API enabled (client id/secret present).")
    else:
        logger.info("[NAVER] client id/secret missing. Naver part will be skipped.")

    last_error: Optional[Exception] = None

    for attempt in range(1, RETRY_MAX_ATTEMPTS + 1):
        try:
            store.mark_running(run_date, attempt)
            logger.info(f"[{run_date}] Attempt #{attempt} started. Status=RUNNING")

            sections_render: Dict[str, List[RenderItem]] = {}

            for sec in SECTIONS:
                logger.info(f"[SECTION] {sec} started.")

                hk_raw = fetch_hankyung_rss(sec)
                hk_sel = _select_latest(hk_raw, w_start, w_end, HK_TOP_N)

                logger.info(f"[HK] {sec} raw={len(hk_raw)} selected={len(hk_sel)}")
                _log_top_titles(logger, "HK_SEL", sec, hk_sel, limit=3)

                nv_filtered: List[NaverNewsItem] = []
                nv_used_sort = ""

                query = NAVER_QUERIES.get(sec, sec)
                logger.info(f"[NAVER_QUERY] {sec} query='{query}' (from NAVER_QUERIES.get(sec, sec))")

                if naver_api:
                    items, used = naver_api.search_sim_then_date(query=query, display=100)
                    items = items or []
                    nv_used_sort = used
                    logger.info(f"[NAVER_FETCH] {sec} primary_sort_used={used} raw={len(items)}")
                    logger.info(f"[NAVER_DEBUG] {sec} type(items)={type(items)}")

                    from src.naver_search_api import is_naver_news_link
                    items = [x for x in items if is_naver_news_link(x)]
                    nv_filtered = [x for x in items if _within_window(x.pubdate_kst, w_start, w_end)]
                    logger.info(f"[NAVER_FILTER] {sec} after_window filtered={len(nv_filtered)}")

                    if len(nv_filtered) < NAVER_TOP_N:
                        logger.info(f"[NAVER_FALLBACK] {sec} filtered<{NAVER_TOP_N}. fallback to sort=date with SAME query='{query}'")
                        items2 = naver_api.search_date(query=query, display=100)
                        items2 = items2 or []
                        logger.info(f"[NAVER_FETCH] {sec} fallback_sort=date raw={len(items2)}")
                        items2 = [x for x in items2 if is_naver_news_link(x)]
                        nv_filtered = [x for x in items2 if _within_window(x.pubdate_kst, w_start, w_end)]
                        nv_used_sort = "date"
                        logger.info(f"[NAVER_FILTER] {sec} after_window(filtered by date) filtered={len(nv_filtered)}")

                    nv_filtered.sort(key=lambda x: x.pubdate_kst or 0, reverse=True)
                    nv_filtered = nv_filtered[:NAVER_TOP_N]
                    logger.info(f"[NAVER_FINAL] {sec} used_sort={nv_used_sort} final={len(nv_filtered)}")
                else:
                    logger.info(f"[NAVER] {sec} skipped.")

                used_nv_idx = set()
                hk_to_nv: Dict[int, Optional[NaverNewsItem]] = {}

                for i, hk in enumerate(hk_sel):
                    best_j = -1
                    best_score = 0.0
                    for j, nv in enumerate(nv_filtered):
                        if j in used_nv_idx:
                            continue
                        score = _jaccard(hk.title, nv.title)
                        if score > best_score:
                            best_score = score
                            best_j = j

                    if best_j >= 0 and best_score >= 0.35:
                        hk_to_nv[i] = nv_filtered[best_j]
                        used_nv_idx.add(best_j)
                        logger.info(
                            f"[MATCH_DETAIL] {sec} HK#{i} matched NV#{best_j} score={best_score:.2f} "
                            f"HK='{hk.title[:60]}' | NV='{nv_filtered[best_j].title[:60]}'"
                        )
                    else:
                        hk_to_nv[i] = None
                        logger.info(
                            f"[MATCH_DETAIL] {sec} HK#{i} no match (best={best_score:.2f}) "
                            f"HK='{hk.title[:60]}'"
                        )

                overlap = sum(1 for v in hk_to_nv.values() if v is not None)
                logger.info(f"[MATCH] {sec} overlap={overlap} (out of {len(hk_sel)})")

                render_items: List[RenderItem] = []

                for i, hk in enumerate(hk_sel):
                    published = fmt_dt(hk.published_kst) if hk.published_kst else "NO_DATE"
                    nv = hk_to_nv.get(i)

                    if nv and nv.pubdate_kst:
                        src_line = f"출처/작성시간: 한국경제({published}), 네이버 뉴스({fmt_dt(nv.pubdate_kst)})"
                    else:
                        src_line = f"출처/작성시간: 한국경제({published})"

                    hk_text = fetch_article_text(hk.link)
                    logger.info(f"[FETCH] {sec} HK#{i} text_len={len(hk_text)} url={hk.link}")

                    related_texts: List[str] = []
                    if nv:
                        if (nv.description or "").strip():
                            related_texts.append((nv.description or "").strip())
                            logger.info(f"[RELATED_TEXT] {sec} HK#{i} add naver description len={len(related_texts[-1])}")
                        else:
                            logger.info(f"[RELATED_TEXT] {sec} HK#{i} naver description empty.")
                    else:
                        logger.info(f"[RELATED_TEXT] {sec} HK#{i} no matched naver.")

                    body_html = rewrite_article_grounded(
                        title=hk.title,
                        article_text=hk_text,
                        published_dt_str=published,
                        section=sec,
                        related_texts=related_texts,
                    )
                    logger.info(f"[GPT] {sec} HK#{i} body_html_len={len(body_html)}")

                    main_links_html = f"원문 링크: <a href='{hk.link}'>자세히 보기(한국경제)</a>"

                    rels: List[str] = []
                    if nv:
                        rels.append(f"<a href='{nv.link}'>관련기사1(네이버)</a>")

                    related_links_html = ""
                    if rels:
                        related_links_html = "관련기사: " + ", ".join(rels)

                    render_items.append(RenderItem(
                        section=sec,
                        title=f"{sec} | {hk.title}",
                        source_line=src_line,
                        body_html=body_html,
                        main_links_html=main_links_html,
                        related_links_html=related_links_html,
                        is_extra=False
                    ))

                extras: List[RenderItem] = []
                for j, nv in enumerate(nv_filtered):
                    if j in used_nv_idx:
                        continue

                    dt = fmt_dt(nv.pubdate_kst) if nv.pubdate_kst else "NO_DATE"
                    source_line = f"출처/작성시간: <a href='{nv.link}'>네이버 뉴스({dt})</a>"

                    extras.append(RenderItem(
                        section=sec,
                        title=f"{sec} | {nv.title}",
                        source_line=source_line,
                        body_html="",
                        main_links_html="",
                        related_links_html="",
                        is_extra=True,
                    ))

                logger.info(f"[EXTRA] {sec} nv_total={len(nv_filtered)} used_for_match={len(used_nv_idx)} extras={len(extras)}")
                _log_top_titles(logger, "EXTRA_SEL", sec, extras, limit=3)

                render_items.extend(extras[:2])

                sections_render[sec] = render_items
                logger.info(f"[SECTION] {sec} done. render_items={len(render_items)} (main={len(hk_sel)}, extra={min(len(extras), 2)})")

            date_title = fmt_date(now)
            blog_title = BLOG_TITLE_FMT.format(date=date_title)
            mail_subject = MAIL_SUBJECT_FMT.format(date=date_title)

            logger.info(f"[RENDER] building HTML title='{blog_title}' subject='{mail_subject}'")
            newsletter_html = render_newsletter_html(
                top_note_html=TOP_NOTE,
                title=blog_title,
                sections=sections_render,
            )
            logger.info(f"[RENDER] HTML built len={len(newsletter_html)}")

            out_dir = Path("output")
            out_dir.mkdir(exist_ok=True)

            html_path = out_dir / f"newsletter_{run_date}.html"
            html_path.write_text(newsletter_html, encoding="utf-8")
            logger.info(f"[FILE] newsletter html saved: {html_path}")

            txt_path = out_dir / f"newsletter_{run_date}.txt"
            blog_tags = "경제, 한국경제, 미국경제, IT, Tech, 뉴스, 네이버, 미국, 엔비디아, 구글"
            separator = "\n\n"
            txt_content = f"{blog_title}{separator}{blog_tags}{separator}{newsletter_html}"
            txt_path.write_text(txt_content, encoding="utf-8")
            logger.info(f"[FILE] newsletter txt saved: {txt_path}")

            if recipients:
                logger.info(f"[MAIL] send start to={recipients} subject='{mail_subject}' html_len={len(newsletter_html)}")
                send_mail_via_outlook_app(
                    to_addrs=recipients,
                    subject=mail_subject,
                    html_body=newsletter_html,
                )
                logger.info("[MAIL] send success.")
                logger.info(f"[{run_date}] Mail sent successfully (HTML).")
            else:
                logger.info(f"[{run_date}] Recipients empty. Skip sending mail.")

            # ✅ TXT 열기 (왼쪽 스냅)
            txt_proc = subprocess.Popen(["notepad.exe", str(txt_path)])
            time.sleep(0.8)
            
            # 창 왼쪽 스냅 (notepad가 활성창이어야 함)
            try:
                import pyautogui
                pyautogui.hotkey("win", "left")
            except Exception as e:
                logger.warning(f"[SNAP] left snap failed (install pyautogui?): {e}")

            # ✅ 티스토리 로그인 스크립트 실행 (별도 프로세스)
            _launch_tistory_login_only(logger, script_path="src/tistory_login_only.py")

            store.mark_success(run_date, attempt)
            logger.info(f"[{run_date}] FINAL SUCCESS after {attempt} attempt(s).")
            return

        except Exception as e:
            last_error = e
            store.mark_failed(run_date, attempt, str(e))
            logger.error(f"Attempt #{attempt} failed: {e}")

            if attempt < RETRY_MAX_ATTEMPTS:
                logger.info(f"Retrying in {RETRY_INTERVAL_SEC} seconds...")
                time.sleep(RETRY_INTERVAL_SEC)

    logger.error(f"[{run_date}] FINAL FAILED after {RETRY_MAX_ATTEMPTS} attempt(s). Reason: {last_error}")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
