"""주간 뉴스 브리프 HTML 이메일 생성기 (주간브리프.pdf 포맷 기준)"""

import argparse
import base64
import html
import json
import os
import re
import webbrowser
from pathlib import Path

# ── 색상 상수 ──────────────────────────────────────────────────────────────────
C_HEADER_BG     = "#1a2a4a"  # 네이비 (헤더/타이틀/버튼)
C_ACCENT        = "#d94e3e"  # 코랄 (헤더 그래픽 기본 색)
C_KEY_ISSUE_R   = "#cfe3e1"  # 핵심이슈 우측 (민트/시안)
C_KEY_ISSUE_L   = "#e7ebee"  # 핵심이슈 좌측 (연회색)
C_CARD_BG       = "#f2f2f2"  # 기사카드 배경
C_DIVIDER       = "#d0d0d0"  # 구분선
C_SOURCE        = "#888888"  # 출처/날짜 텍스트
C_SUMMARY       = "#555555"  # 요약 텍스트
C_SUBTITLE      = "#666666"  # 주차/기간 서브타이틀
C_OUTER_BG      = "#ffffff"  # 페이지 배경
C_WHITE         = "#ffffff"

FONT   = '"Malgun Gothic", "Apple SD Gothic Neo", "나눔고딕", Arial, sans-serif'
MAX_W  = 720

# 외부 호스팅 이미지 (메일 클라이언트 호환 — Outlook 등이 data:URI/CSS background를 차단해도 동작)
# GitHub raw URL 사용 (HTTPS 필수 — 메일 클라이언트의 mixed content 차단 회피)
DEFAULT_HEADER_URL = "https://raw.githubusercontent.com/muchwater/FINSTP/main/header_background.jpg"
DEFAULT_LOGO_URL   = "https://raw.githubusercontent.com/muchwater/FINSTP/main/FINSTP_logo.png"

MIME_MAP = {
    ".png":  "image/png",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif":  "image/gif",
    ".svg":  "image/svg+xml",
}


# ── 유틸리티 ───────────────────────────────────────────────────────────────────

def load_image_b64(path: str) -> str:
    if not path:
        return ""
    # HTTP(S) URL은 그대로 반환 (메일 클라이언트 호환을 위해 외부 호스팅 권장)
    if path.startswith(("http://", "https://")):
        return path
    if not os.path.isfile(path):
        return ""
    ext  = os.path.splitext(path)[1].lower()
    mime = MIME_MAP.get(ext, "image/png")
    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def esc(text) -> str:
    return html.escape(str(text))


def slug(period: str) -> str:
    m = re.search(r"(\d+)년\s*(\d+)월\s*(\d+)주차", period)
    if m:
        year, month, week = m.group(1), m.group(2).zfill(2), m.group(3)
        return f"{year}_{month}_w{week}"
    return re.sub(r"[^\w]", "_", period)


# ── 섹션 빌더 ──────────────────────────────────────────────────────────────────

def _format_paragraph(text: str) -> str:
    """여러 줄 문자열을 HTML 로 변환.
    빈 줄(\\n\\n)은 문단 구분, 한 줄 개행(\\n)은 <br>.
    """
    if not text:
        return ""
    escaped = esc(text)
    paragraphs = escaped.split("\n\n")
    rendered = []
    for i, p in enumerate(paragraphs):
        body = p.strip("\n").replace("\n", "<br>")
        margin = "0" if i == 0 else "12px 0 0 0"
        rendered.append(
            f'<p style="margin:{margin};font-size:14px;color:#2c3e50;font-family:{FONT};line-height:1.75;">{body}</p>'
        )
    return "\n".join(rendered)


def build_greeting(text: str, position: str = "top") -> str:
    """인사문구(상용구) 섹션. position='top'이면 헤더 위, 'continued'면 직전 그리팅에 이어서, 'bottom'이면 푸터 아래."""
    if not text:
        return ""
    if position == "top":
        padding = "28px 44px 18px 44px"
    elif position == "continued":
        padding = "0 44px 28px 44px"
    else:
        padding = "14px 44px 36px 44px"
    return f"""<tr>
<td bgcolor="{C_WHITE}" style="background:{C_WHITE};padding:{padding};">
{_format_paragraph(text)}
</td>
</tr>"""


def build_head(period: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="ko" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<!--[if gte mso 9]>
<xml>
<o:OfficeDocumentSettings>
<o:AllowPNG/>
<o:PixelsPerInch>96</o:PixelsPerInch>
</o:OfficeDocumentSettings>
</xml>
<![endif]-->
<!--[if mso]>
<style type="text/css">
body, table, td, p, span, a {{ font-family: Arial, sans-serif !important; }}
</style>
<![endif]-->
</head>"""


def build_header(period: str, date_range: str, header_img_uri: str) -> str:
    """헤더 = 단일 이미지(타이틀 텍스트가 이미지에 미리 렌더링되어 있음).
    이미지가 있으면 <img> 한 장으로 표시 → 모든 메일 클라이언트에서 동일하게 보임.
    이미지가 없으면 기존 CSS 헤더(네이비 배경 + HTML 텍스트 + 줄무늬)로 폴백.
    이미지 아래 흰색 영역에 '주차 주요 기사 모음' / '기간:' + 구분선 유지.
    """
    if header_img_uri:
        header_block = f"""<tr>
<td bgcolor="{C_WHITE}" style="background:{C_WHITE};padding:24px 44px 0 44px;">
<img src="{header_img_uri}" alt="KAIST 국가미래전략기술 정책연구소 — 주간 뉴스 브리프" width="632" style="display:block;width:100%;max-width:632px;height:auto;border:0;">
</td>
</tr>"""
    else:
        # 폴백: CSS 헤더 (이미지가 없을 때만)
        title_block = f"""<p style="margin:0 0 14px 0;font-size:17px;color:{C_WHITE};font-family:{FONT};letter-spacing:2px;font-weight:500;">KAIST 국가미래전략기술 정책연구소</p>
<h1 style="margin:0;font-size:48px;font-weight:600;color:{C_WHITE};font-family:{FONT};letter-spacing:2px;line-height:1.15;">주간 뉴스 브리프</h1>"""
        stripes = f"""<td align="right" valign="top" width="220" style="padding-left:16px;">
<table cellpadding="0" cellspacing="0" border="0" style="display:inline-table;">
<tr>
<td width="18" style="background:{C_ACCENT};height:140px;">&nbsp;</td>
<td width="6"  style="background:{C_HEADER_BG};height:140px;">&nbsp;</td>
<td width="18" style="background:{C_ACCENT};height:140px;">&nbsp;</td>
<td width="6"  style="background:{C_HEADER_BG};height:140px;">&nbsp;</td>
<td width="18" style="background:{C_ACCENT};height:140px;">&nbsp;</td>
<td width="6"  style="background:{C_HEADER_BG};height:140px;">&nbsp;</td>
<td width="18" style="background:{C_ACCENT};height:140px;">&nbsp;</td>
</tr>
</table>
</td>"""
        header_block = f"""<tr>
<td bgcolor="{C_WHITE}" style="background:{C_WHITE};padding:24px 44px 0 44px;">
<table width="100%" cellpadding="0" cellspacing="0" border="0">
<tr>
<td bgcolor="{C_HEADER_BG}" style="background-color:{C_HEADER_BG};padding:28px 36px 30px 36px;" height="160">
<table width="100%" cellpadding="0" cellspacing="0" border="0">
<tr>
<td valign="middle" style="padding:20px 0;">
{title_block}
</td>
{stripes}
</tr>
</table>
</td>
</tr>
</table>
</td>
</tr>"""

    subtitle_block = f"""<tr>
<td bgcolor="{C_WHITE}" style="background:{C_WHITE};padding:16px 44px 10px 44px;">
<table width="100%" cellpadding="0" cellspacing="0" border="0">
<tr>
<td valign="middle" style="font-size:13px;color:{C_SUBTITLE};font-family:{FONT};letter-spacing:1px;">{esc(period)} 주요 기사 모음</td>
<td align="right" valign="middle" style="font-size:13px;color:{C_SUBTITLE};font-family:{FONT};letter-spacing:1px;">기간: {esc(date_range)}</td>
</tr>
</table>
</td>
</tr>
<tr>
<td bgcolor="{C_WHITE}" style="background:{C_WHITE};padding:0 44px;">
<table width="100%" cellpadding="0" cellspacing="0" border="0">
<tr><td style="border-top:1px solid {C_DIVIDER};font-size:0;line-height:0;">&nbsp;</td></tr>
</table>
</td>
</tr>"""

    return header_block + subtitle_block


def build_key_issues(issues: list) -> str:
    """PDF 좌측 연회색 박스('이번 주 / 핵심 이슈' + 폴더아이콘) + 우측 민트 박스(불릿)."""
    bullets_html = ""
    for i, issue in enumerate(issues):
        margin = "0" if i == len(issues) - 1 else "0 0 8px 0"
        bullets_html += f"""<p style="margin:{margin};font-size:14px;color:{C_HEADER_BG};font-weight:700;font-family:{FONT};line-height:1.5;letter-spacing:-0.3px;">&middot;&nbsp;{esc(issue)}</p>
"""

    return f"""<tr>
<td bgcolor="{C_WHITE}" style="background:{C_WHITE};padding:28px 44px 20px 44px;">
<table width="100%" cellpadding="0" cellspacing="0" border="0">
<tr>
<td width="92" valign="middle" bgcolor="{C_KEY_ISSUE_L}" style="background:{C_KEY_ISSUE_L};padding:18px 14px;">
<p style="margin:0;font-size:17px;color:{C_HEADER_BG};font-family:{FONT};font-weight:500;letter-spacing:2px;line-height:1.5;text-align:center;">이번 주<br>핵심 이슈</p>
</td>
<td valign="middle" bgcolor="{C_KEY_ISSUE_R}" style="background:{C_KEY_ISSUE_R};padding:22px 30px;">
{bullets_html}
</td>
</tr>
</table>
</td>
</tr>"""


def build_article_card(article: dict, is_first: bool) -> str:
    """각 기사 카드는 개별 회색 박스로 상하 여백 분리."""
    top_pad = "6px" if is_first else "14px"

    # 사각형 카테고리 뱃지 (흰 배경 + 얇은 네이비 테두리)
    badge = f"""<table cellpadding="0" cellspacing="0" border="0" style="display:inline-table;">
<tr><td style="border:1px solid {C_HEADER_BG};padding:4px 12px;font-size:12px;color:{C_HEADER_BG};font-weight:600;font-family:{FONT};white-space:nowrap;background:{C_WHITE};letter-spacing:-0.2px;">{esc(article.get('category', ''))}</td></tr>
</table>"""

    # 사각형 '원문 읽기' 버튼 (화살표 없음, 네이비 배경)
    url = esc(article.get("url", "#"))
    btn = f"""<a href="{url}" target="_blank" style="display:inline-block;padding:6px 16px;background:{C_HEADER_BG};color:{C_WHITE};font-size:11px;font-weight:600;text-decoration:none;font-family:{FONT};white-space:nowrap;letter-spacing:-0.2px;">원문 읽기</a>"""

    return f"""<tr>
<td bgcolor="{C_WHITE}" style="background:{C_WHITE};padding:{top_pad} 44px 0 44px;">
<table width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="{C_CARD_BG}" style="background:{C_CARD_BG};">
<tr>
<td style="padding:18px 22px;">
<table width="100%" cellpadding="0" cellspacing="0" border="0">
<tr>
<td valign="middle">{badge}</td>
<td valign="middle" align="right" style="padding:0 10px;">
<span style="font-size:12px;color:{C_SOURCE};font-family:{FONT};">{esc(article.get('source', ''))}&nbsp;&nbsp;|&nbsp;&nbsp;{esc(article.get('date', ''))}</span>
</td>
<td align="right" valign="middle" width="82">{btn}</td>
</tr>
<tr>
<td colspan="3" style="padding-top:10px;">
<p style="margin:0;font-size:20px;font-weight:700;color:{C_HEADER_BG};font-family:{FONT};line-height:1.3;letter-spacing:-0.5px;">{esc(article.get('title', ''))}</p>
</td>
</tr>
<tr>
<td colspan="3" style="padding-top:4px;">
<p style="margin:0;font-size:13px;color:{C_SUMMARY};font-family:{FONT};line-height:1.6;">{esc(article.get('summary', ''))}</p>
</td>
</tr>
</table>
</td>
</tr>
</table>
</td>
</tr>"""


def build_footer(logo_uri: str) -> str:
    """KAIST FINSTP 로고 이미지를 우측 하단에 배치. 구분선·박스 없음."""
    if logo_uri:
        logo_block = f"""<img src="{logo_uri}" alt="KAIST Future Institute for National Strategic Technology &amp; Policy" width="360" style="display:inline-block;max-width:360px;height:auto;border:0;">"""
    else:
        # 이미지 없을 때 텍스트 대체
        logo_block = f"""<table cellpadding="0" cellspacing="0" border="0" style="display:inline-table;">
<tr>
<td valign="middle" style="padding-right:14px;">
<span style="color:{C_HEADER_BG};font-size:22px;font-weight:900;letter-spacing:1.5px;font-family:Arial,sans-serif;">KAIST</span>
</td>
<td valign="middle" align="left">
<p style="margin:0;font-size:12px;font-weight:700;color:{C_HEADER_BG};font-family:{FONT};line-height:1.4;">Future Institute for National</p>
<p style="margin:0;font-size:12px;font-weight:700;color:{C_HEADER_BG};font-family:{FONT};line-height:1.4;">Strategic Technology &amp; Policy (FINST&amp;P)</p>
<p style="margin:3px 0 0 0;font-size:11px;color:#555;font-family:{FONT};line-height:1.4;">KAIST 국가미래전략기술 정책연구소</p>
</td>
</tr>
</table>"""

    return f"""<tr>
<td bgcolor="{C_WHITE}" style="background:{C_WHITE};padding:50px 44px 40px 44px;">
<table width="100%" cellpadding="0" cellspacing="0" border="0">
<tr>
<td align="right">
{logo_block}
</td>
</tr>
</table>
</td>
</tr>"""


# ── 오케스트레이터 ─────────────────────────────────────────────────────────────

def generate_html(data: dict, header_img_path: str = "", logo_path: str = "") -> str:
    parts = [build_head(data.get("period", ""))]
    parts.append(f'<body style="margin:0;padding:0;background:{C_OUTER_BG};">')

    # 외부 래퍼
    parts.append(f'<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{C_OUTER_BG};">')
    parts.append('<tr><td align="center" style="padding:20px 16px;">')

    # 메인 테이블
    parts.append(f'<table width="{MAX_W}" cellpadding="0" cellspacing="0" border="0" style="max-width:{MAX_W}px;width:100%;background:{C_WHITE};">')

    # 상단 인사문구 (greeting + closing 이어서 배치)
    parts.append(build_greeting(data.get("greeting", ""), position="top"))
    parts.append(build_greeting(data.get("closing", ""), position="continued"))

    parts.append(build_header(
        data.get("period", ""),
        data.get("date_range", ""),
        load_image_b64(header_img_path),
    ))
    parts.append(build_key_issues(data.get("key_issues", [])))

    articles = data.get("articles", [])
    for i, article in enumerate(articles):
        parts.append(build_article_card(article, is_first=(i == 0)))

    if not articles:
        parts.append(f'<tr><td bgcolor="{C_WHITE}" style="background:{C_WHITE};padding:32px 44px;text-align:center;"><p style="margin:0;color:{C_SOURCE};font-family:{FONT};font-size:13px;">등록된 기사가 없습니다.</p></td></tr>')

    parts.append(build_footer(load_image_b64(logo_path)))

    parts.append("</table>")  # /메인 테이블
    parts.append("</td></tr></table>")  # /외부 래퍼
    parts.append("</body></html>")

    return "\n".join(parts)


# ── CLI ────────────────────────────────────────────────────────────────────────

def _default_image(root: Path, *candidates: str) -> str:
    for name in candidates:
        p = root / name
        if p.is_file():
            return str(p)
    return ""


def main():
    parser = argparse.ArgumentParser(
        description="주간 뉴스 브리프 HTML 이메일 생성기",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""예시:
  python generate_brief.py sample_data.json
  python generate_brief.py sample_data.json --open
  python generate_brief.py sample_data.json --header-img images/header_bg.jpg --logo images/kaist.png
""",
    )
    parser.add_argument("json_file", help="입력 JSON 파일 경로")
    parser.add_argument("--header-img", default="", metavar="PATH",
                        help="헤더 배경 이미지 경로. 미지정 시 images/header background.jpg 자동 사용.")
    parser.add_argument("--logo", default="", metavar="PATH",
                        help="KAIST FINSTP 로고 이미지 경로. 미지정 시 images/FINSTP logo.png 자동 사용.")
    parser.add_argument("--output", default="", metavar="PATH",
                        help="출력 HTML 파일 경로. 기본값: output/brief_<주차>.html")
    parser.add_argument("--open", action="store_true",
                        help="생성 후 기본 브라우저로 바로 열기")
    args = parser.parse_args()

    json_path = Path(args.json_file)
    if not json_path.exists():
        parser.error(f"파일을 찾을 수 없습니다: {args.json_file}")

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    # 이미지 우선순위: --flag > 로컬 images/ 폴더 (base64 인라인 임베드) > 외부 호스팅 URL(fallback)
    # base64 인라인이 메일 작성창(특히 Outlook)에서 inline 첨부로 자동 변환되어 가장 안정적
    images_root = Path.cwd() / "images"
    header_img = (
        args.header_img
        or _default_image(images_root, "header_background_embed.png", "header_background_embed.jpg", "header_background.jpg", "header background.jpg", "header.jpg", "header.png")
        or DEFAULT_HEADER_URL
    )
    logo_img = (
        args.logo
        or _default_image(images_root, "FINSTP_logo.jpg", "FINSTP_logo.png", "FINSTP logo.png", "FINSTP logo.jpg", "kaist_logo.png", "kaist.png")
        or DEFAULT_LOGO_URL
    )

    html_str = generate_html(
        data,
        header_img_path=header_img,
        logo_path=logo_img,
    )

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        out_dir = json_path.parent / "output"
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / f"brief_{slug(data.get('period', 'output'))}.html"

    out_path.write_text(html_str, encoding="utf-8")
    print(f"생성 완료: {out_path.resolve()}")
    if header_img:
        print(f"  헤더 이미지: {header_img}")
    if logo_img:
        print(f"  로고 이미지: {logo_img}")

    if args.open:
        webbrowser.open(out_path.resolve().as_uri())


if __name__ == "__main__":
    main()
