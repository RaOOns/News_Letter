from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any, List
import json
import os

from openai import OpenAI


@dataclass
class RewriteResult:
    ok: bool
    body: str
    importance: str
    reason_if_fail: Optional[str] = None


def _build_prompt(title: str, published_kst: str, article_text: str, related_texts: List[str]) -> str:
    related_block = ""
    if related_texts:
        chunks = [f"[관련자료 {i}]\n{t}" for i, t in enumerate(related_texts, start=1)]
        related_block = "\n\n" + "\n\n".join(chunks)

    return f"""
너는 뉴스레터/블로그 글 편집자다. 아래 제공 텍스트(기사 원문 및 관련자료)만을 근거로 글을 풍부하게 다듬어라.

절대 규칙(중요):
- 제공 텍스트 밖의 사실/수치/배경/원인/전망을 추가하지 말 것.
- 확실하지 않으면 반드시 "제공 텍스트만으로 확인 불가"라고 명시할 것.
- 과장/추측/단정 금지.
- 출력은 반드시 JSON 하나만 반환할 것. (코드블록 금지)
- 출력에는 '제목/작성시간/링크'를 포함하지 말 것.

출력 JSON 스키마:
{{
  "body": "2~5문장. 블로그에 올릴 문장 톤. 과장 금지. 제공 텍스트 근거만.",
  "importance": "HIGH|MEDIUM|LOW",
  "evidence_quotes": ["제공 텍스트에서 직접 인용한 근거 구절 1", "근거 구절 2", "근거 구절 3(선택)"]
}}

작성시간(참고용, 출력에 포함하지 말 것):
- {published_kst}

[메타정보]
- 제목: {title}

[기사 원문]
{article_text}
{related_block}
""".strip()


def rewrite_grounded(
    client: OpenAI,
    model: str,
    title: str,
    published_kst: str,
    article_text: str,
    related_texts: Optional[List[str]] = None,
) -> RewriteResult:
    related_texts = related_texts or []
    prompt = _build_prompt(title, published_kst, article_text, related_texts)

    resp = client.responses.create(model=model, input=prompt)
    out = resp.output_text.strip()

    try:
        data: Dict[str, Any] = json.loads(out)
        body = (data.get("body") or "").strip()
        importance = (data.get("importance") or "").strip()
        quotes: List[str] = data.get("evidence_quotes") or []

        corpus = article_text + "\n" + "\n".join(related_texts)
        valid_quotes = [q for q in quotes if isinstance(q, str) and q.strip() and q.strip() in corpus]

        if not body:
            return RewriteResult(False, "", "", "Missing body.")
        if importance not in {"HIGH", "MEDIUM", "LOW"}:
            return RewriteResult(False, "", "", "Invalid importance.")
        if len(valid_quotes) < 2:
            return RewriteResult(False, "", "", "Not enough grounded evidence quotes.")

        return RewriteResult(True, body, importance)

    except Exception as e:
        return RewriteResult(False, "", "", f"JSON parse/validation error: {e}")


def _text_to_html(s: str) -> str:
    if not s:
        return "<p>요약을 생성하지 못했습니다.</p>"
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    s = s.replace("\n", "<br/>")
    return f"<p style='margin:0 0 10px 0; line-height:1.6;'>{s}</p>"


# ✅ run.py가 import해서 쓰는 고정 함수명
def rewrite_article_grounded(
    title: str,
    article_text: str,
    published_dt_str: str,
    section: str,
    related_texts: Optional[List[str]] = None,
) -> str:
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    model = (os.getenv("OPENAI_MODEL") or "gpt-4.1-mini").strip()

    # 키 없으면 “근거 기반(원문 발췌)”로만
    if not api_key:
        fallback = (article_text or "").strip()
        if len(fallback) > 800:
            fallback = fallback[:800] + "…"
        return _text_to_html(fallback)

    client = OpenAI(api_key=api_key)
    res = rewrite_grounded(
        client=client,
        model=model,
        title=title,
        published_kst=published_dt_str or "",
        article_text=article_text or "",
        related_texts=related_texts or [],
    )

    if not res.ok:
        fallback = (article_text or "").strip()
        if len(fallback) > 800:
            fallback = fallback[:800] + "…"
        return _text_to_html(fallback)

    return _text_to_html(res.body)
