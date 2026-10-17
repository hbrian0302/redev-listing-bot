"""매물 데이터 → 카드 PNG(1080²). single=1장, carousel=슬라이드별 N장."""
from pathlib import Path
from typing import List
from jinja2 import Environment, FileSystemLoader, select_autoescape
from playwright.async_api import async_playwright
from schema import decide_layout

TPL_DIR = Path(__file__).resolve().parent / "templates"
ALLOWED_LAYOUTS = frozenset({"single", "carousel"})
_env = Environment(loader=FileSystemLoader(str(TPL_DIR)),
                   autoescape=select_autoescape(["html"]))


def _render_html(data: dict, layout: str) -> str:
    if layout not in ALLOWED_LAYOUTS:
        raise ValueError(f"invalid layout: {layout}")
    return _env.get_template(f"{layout}.html").render(**data)


async def render_card(data: dict, out_dir: Path, stem: str) -> List[Path]:
    """카드 PNG 생성. 반환: 생성된 PNG 경로 리스트(순서=슬라이드 순)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    layout = decide_layout(data)
    html = _render_html(data, layout)
    paths: List[Path] = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        try:
            page = await browser.new_page(viewport={"width": 1080, "height": 1080},
                                          device_scale_factor=1)
            await page.set_content(html, wait_until="networkidle")
            if layout == "single":
                fp = out_dir / f"{stem}.png"
                await page.screenshot(path=str(fp),
                                      clip={"x": 0, "y": 0, "width": 1080, "height": 1080})
                paths.append(fp)
            else:
                slides = await page.query_selector_all(".slide")
                for i, sl in enumerate(slides, 1):
                    fp = out_dir / f"{stem}_{i}.png"
                    await sl.screenshot(path=str(fp))
                    paths.append(fp)
        finally:
            await browser.close()
    return paths
