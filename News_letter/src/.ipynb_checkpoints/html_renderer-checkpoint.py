from dataclasses import dataclass
from typing import Dict, List
import re


@dataclass
class RenderItem:
    section: str
    title: str
    source_line: str
    body_html: str
    main_links_html: str
    related_links_html: str
    is_extra: bool = False


def _style_main_links_html(s: str) -> str:
    """
    run.py에서 만들어진 main_links_html 문자열을
    - '원문 링크:' 라벨은 span.link-label로 감싸서 source-line과 동일 색(#666) 적용
    - 링크는 a.main-link로 클래스 부여해서 header-title과 같은 색(#1f5d2b) + 굵게 적용
    """
    if not s:
        return ""

    out = s

    # 1) '원문 링크:' 라벨 감싸기 (이미 감싸져 있으면 중복 방지)
    if "원문 링크:" in out and "link-label" not in out:
        out = out.replace("원문 링크:", "<span class='link-label'>원문 링크:</span>", 1)

    # 2) <a ...>에 main-link 클래스 주입 (class가 없을 수도/있을 수도)
    def _inject_class(match: re.Match) -> str:
        tag = match.group(0)
        # 이미 main-link가 있으면 그대로
        if "main-link" in tag:
            return tag

        if "class=" in tag:
            # 기존 class에 main-link 추가
            return re.sub(r"class=(['\"])(.*?)\1", r"class=\1\2 main-link\1", tag, count=1)
        else:
            # class 속성 추가
            return tag[:-1] + " class='main-link'>"

    out = re.sub(r"<a\b[^>]*>", _inject_class, out)

    return out


def render_newsletter_html(
    top_note_html: str,
    title: str,
    sections: Dict[str, List[RenderItem]],
) -> str:
    html = []

    html.append("""
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8"/>
<style>
body {
    font-family: "Apple SD Gothic Neo", "Noto Sans KR", Arial, sans-serif;
    line-height: 1.65;
    color: #222;
}
.wrapper {
    max-width: 860px;
    margin: 0 auto;
}
.header-box {
    background: #f7f3ee;
    border: 1px solid #d7c7b8;
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 30px;
}
.header-title {
    font-size: 22px;
    font-weight: 900;  /* 🔥 더 굵게 */
    color: #1f5d2b;
    margin-bottom: 8px;
}
.header-note {
    font-size: 14px;
    color: #555;
    line-height: 1.35;
}
.section-title {
    font-size: 20px;
    font-weight: 700;
    color: #5a3a26;
    margin-top: 36px;
    padding-bottom: 6px;
    border-bottom: 3px solid #b38b6d;
}
.article {
    margin-top: 24px;
    padding-bottom: 24px;
    border-bottom: 1px solid #e3e3e3;
}
.article-title {
    font-size: 18px;
    font-weight: 800;  /* 🔥 기사 제목 더 굵게 */
    margin-bottom: 6px;
}
.source-line {
    font-size: 13px;
    color: #666;
    margin-bottom: 10px;
}
.body {
    font-size: 15px;
    margin-bottom: 10px;
}
.links {
    font-size: 14px;
}

/* ✅ [요청 1] "원문 링크" 라벨을 출처/작성시간과 동일 색으로 */
.link-label {
    color: #666;        /* source-line과 동일 */
    font-weight: normal;
}

/* ✅ [요청 2] "자세히 보기(플랫폼)" 링크를 헤더 타이틀과 같은 색 + 굵게 */
a.main-link {
    color: #1f5d2b;     /* header-title과 동일 */
    font-weight: 900;   /* 더 굵게 */
    text-decoration: none;
}
a.main-link:hover {
    text-decoration: underline;
}

/* 기존 links a 스타일은 유지하되,
   main-link가 있으면 위 규칙이 더 구체적이라(main-link) 우선 적용됨 */
.links a {
    color: #1f7a3f;
    font-weight: 800;
    text-decoration: none;
}
.links a:hover {
    text-decoration: underline;
}

.extra {
    background: #fafafa;
    padding: 10px 14px;
    border-radius: 6px;
    margin-top: 10px;
}
</style>
</head>
<body>
<div class="wrapper">
""")

    # 헤더
    html.append(f"""
<div class="header-box">
    <div class="header-title">{title}</div>
    <div class="header-note">{top_note_html}</div>
</div>
""")

    # 섹션별
    for section, items in sections.items():
        html.append(f"<div class='section-title'>{section}</div>")

        for item in items:
            if item.is_extra:
                html.append(f"""
<div class="extra">
    <div class="article-title">{item.title}</div>
    <div class="source-line">{item.source_line}</div>
</div>
""")
                continue

            # ✅ main_links_html만 요청사항대로 가공
            styled_main_links_html = _style_main_links_html(item.main_links_html)

            html.append(f"""
<div class="article">
    <div class="article-title">{item.title}</div>
    <div class="source-line">{item.source_line}</div>
    <div class="body">{item.body_html}</div>
    <div class="links">{styled_main_links_html}</div>
""")

            if item.related_links_html:
                html.append(f"""
    <div class="links">{item.related_links_html}</div>
""")

            html.append("</div>")

    html.append("""
</div>
</body>
</html>
""")

    return "\n".join(html)
