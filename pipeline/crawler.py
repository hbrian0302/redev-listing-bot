"""네이버 블로그 크롤러(다중 블로그). song_han_crawler 일반화.
- 목록: PostTitleListAsync (전체 logNo/제목/날짜)
- 본문: Playwright m.blog PostView
"""
import asyncio, re, html, math
from datetime import datetime
from typing import List, Optional
from urllib.parse import unquote_plus
import requests
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

LIST_API = "https://blog.naver.com/PostTitleListAsync.naver"
MOBILE_VIEW = "https://m.blog.naver.com/PostView.naver?blogId={blog_id}&logNo={log_no}"
COUNT_PER_PAGE = 30
MAX_PAGES = 100
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
TITLE_SELECTORS = [".se-title-text", ".se_textarea", ".pcol1", ".htitle", "h3.tit_h3"]
CONTENT_SELECTORS = [".se-main-container", "#postViewArea", ".post_ct", "#viewTypeSelector"]


def normalize_date(raw: str) -> str:
    m = re.match(r"(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})", raw or "")
    return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else (raw or "").strip()


def parse_list_page(text: str) -> List[dict]:
    posts = []
    for ch in text.split('"logNo":"')[1:]:
        m = re.match(r"(\d+)", ch)
        if not m:
            continue
        tm = re.search(r'"title":"(.*?)"', ch)
        dm = re.search(r'"addDate":"(.*?)"', ch)
        posts.append({
            "log_no": m.group(1),
            "title": html.unescape(unquote_plus(tm.group(1))).strip() if tm else "",
            "date": normalize_date(dm.group(1)) if dm else "",
        })
    return posts


def fetch_post_meta(blog_id: str) -> List[dict]:
    s = requests.Session()
    headers = {"User-Agent": UA, "Referer": f"https://blog.naver.com/{blog_id}"}

    def page(n):
        r = s.get(LIST_API, params={"blogId": blog_id, "currentPage": str(n),
                  "countPerPage": str(COUNT_PER_PAGE), "categoryNo": "", "parentCategoryNo": "",
                  "viewdate": ""}, headers=headers, timeout=15)
        r.raise_for_status()
        return r.text

    first = page(1)
    tm = re.search(r'"totalCount":"?(\d+)"?', first)
    total = int(tm.group(1)) if tm else 0
    pages = min(MAX_PAGES, max(1, math.ceil(total / COUNT_PER_PAGE))) if total else 1
    seen, out = set(), []
    for n in range(1, pages + 1):
        for post in parse_list_page(first if n == 1 else page(n)):
            if post["log_no"] not in seen:
                seen.add(post["log_no"]); out.append(post)
    return out


async def _text_of(page, selectors):
    for sel in selectors:
        try:
            el = await page.query_selector(sel)
        except Exception:
            el = None
        if el:
            t = await el.text_content()
            if t and t.strip():
                return t
    return None


async def fetch_content(blog_id: str, log_no: str) -> Optional[dict]:
    """단일 글 본문 추출. 반환 {title,url,content} 또는 None."""
    url = MOBILE_VIEW.format(blog_id=blog_id, log_no=log_no)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        try:
            page = await (await browser.new_context(user_agent=UA,
                          viewport={"width": 1280, "height": 720})).new_page()
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            except PWTimeout:
                pass
            await asyncio.sleep(0.3)
            title = await _text_of(page, TITLE_SELECTORS)
            title = re.sub(r"\s+", " ", title).strip() if title else ""
            content = await _text_of(page, CONTENT_SELECTORS)
            content = re.sub(r"\s+", " ", content).strip()[:3000] if content else ""
        finally:
            await browser.close()
    if not (title or content):
        return None
    return {"title": title, "url": url, "content": content}
