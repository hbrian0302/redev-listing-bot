"""무순위 다크 3장 카드 렌더(테마 로테이션). ①결정 ②입지점수 ③지도."""
from __future__ import annotations
from pathlib import Path
from playwright.async_api import async_playwright
from themes import WHITE, GRAY, decision_color
from score import ORDER, LAB, FULL


def _css(t):
    BG, TR, ACC = t["bg"], t["track"], t["accent"]
    return f"""*{{margin:0;padding:0;box-sizing:border-box}}
.slide{{width:1080px;height:1080px;background:{BG};color:{WHITE};position:relative;font-family:'Apple SD Gothic Neo',sans-serif}}
.pad{{position:absolute;inset:64px 60px;display:flex;flex-direction:column}}
.top{{display:flex;justify-content:space-between;font-family:'Courier New',monospace;font-size:20px;color:{GRAY}}}
.top b{{color:{WHITE};font-family:'Apple SD Gothic Neo';font-weight:800}}
.pill{{align-self:flex-start;margin-top:38px;border:1.5px solid {ACC};color:{ACC};border-radius:40px;padding:9px 22px;font-size:20px;font-weight:700}}
.h1{{font-size:80px;font-weight:800;line-height:1.05;margin-top:24px;letter-spacing:-2px}}
.sub{{font-size:23px;color:{GRAY};margin-top:16px}}
.cmp{{margin-top:46px}}.crow{{margin-bottom:24px}}
.clab{{display:flex;justify-content:space-between;font-size:23px;color:{GRAY};margin-bottom:10px}}
.clab b{{color:{WHITE};font-weight:800;font-size:27px}}
.cbar{{height:26px;border-radius:13px}}
.dec{{margin-top:18px;font-size:92px;font-weight:800;letter-spacing:-1px}}
.mean{{font-size:33px;font-weight:700;margin-top:8px;line-height:1.4}}
.mean span{{color:{GRAY};font-weight:400;font-size:25px;display:block;margin-top:8px}}
.foot{{margin-top:auto;font-size:16px;color:{GRAY};line-height:1.6}}
.hero{{display:flex;align-items:flex-end;gap:24px;margin-top:12px}}
.big{{font-size:172px;font-weight:800;line-height:0.85;letter-spacing:-4px}}
.big em{{font-style:normal;font-size:42px;color:{GRAY};font-weight:400}}
.gr{{background:{ACC};color:{BG};font-size:50px;font-weight:800;padding:6px 28px;border-radius:14px}}
.rows{{margin-top:38px}}
.frow{{display:grid;grid-template-columns:150px 220px 92px 1fr;align-items:center;gap:16px;padding:13px 0;border-top:1px solid {TR}}}
.frow:first-child{{border-top:none}}
.fname{{font-size:26px;font-weight:700}}.fname b{{color:{ACC};margin-right:8px}}
.ftrack{{height:12px;background:{TR};border-radius:6px}}.ffill{{height:100%;background:{WHITE};border-radius:6px}}
.fscore{{font-size:29px;font-weight:800;text-align:right}}.fscore span{{font-size:16px;color:{GRAY};font-weight:400}}
.freason{{font-size:19px;color:{GRAY}}}
.walk{{display:flex;gap:32px;margin-top:22px;font-size:25px}}
.walk b{{color:{ACC};font-weight:800;display:block;font-size:19px;margin-bottom:4px}}
.mapbox{{margin-top:30px;flex:1;border-radius:20px;overflow:hidden;border:1px solid {TR}}}
.mapbox img{{width:100%;height:100%;object-fit:cover}}"""


def _html(d, t):
    ACC, TR = t["accent"], t["track"]
    DC = decision_color(d["decision"], ACC)
    wb = round(d["bunyang"] / max(d["bunyang"], d["sise"]) * 100)
    ws = round(d["sise"] / max(d["bunyang"], d["sise"]) * 100)
    top = lambda n: f'<div class="top"><b>BRAND</b><span>{n} / 3</span></div>'
    p1 = (f'<div class="slide"><div class="pad">{top(1)}<div class="pill">무순위 · 살까말까</div>'
          f'<div class="h1">{d["name_l1"]}<br>{d["name_l2"]}</div><div class="sub">{d["sub"]}</div>'
          f'<div class="cmp"><div class="crow"><div class="clab"><span>무순위 분양가</span><b>{d["bunyang"]:.2f}억</b></div><div class="cbar" style="width:{wb}%;background:{DC}"></div></div>'
          f'<div class="crow"><div class="clab"><span>인근 신축 시세</span><b>{d["sise"]:.2f}억</b></div><div class="cbar" style="width:{ws}%;background:{TR}"></div></div></div>'
          f'<div class="dec" style="color:{DC}">{d["decision"]}</div><div class="mean">{d["mean"]}<span>{d["tail"]}</span></div>'
          f'<div class="foot">기준: {d["basis"]} · 분양가=공고(옵션·확장 별도) · 시세=최근 실거래 · 참고용</div></div></div>')
    rows = ""
    for k in ORDER:
        s, reason = d["sc"][k]; w = round(s / FULL[k] * 100)
        rows += (f'<div class="frow"><div class="fname"><b>{k}</b> {LAB[k]}</div>'
                 f'<div class="ftrack"><div class="ffill" style="width:{w}%"></div></div>'
                 f'<div class="fscore">{s}<span>/{FULL[k]}</span></div><div class="freason">{reason}</div></div>')
    p2 = (f'<div class="slide"><div class="pad">{top(2)}<div class="pill">입지점수 · 브역대신평공초</div>'
          f'<div class="hero"><div class="big">{d["total"]}<em> /100</em></div><div class="gr">{d["grade"]}</div></div>'
          f'<div class="rows">{rows}</div>'
          f'<div class="foot">역·초·공원=OpenStreetMap 실거리 · 브역대신평초(princesshouse)+공원 · 평지=수도권 가정</div></div></div>')
    w = d.get("walk", {})
    walk = "".join(f'<div><b>{lab}</b>{v}</div>' for lab, v in w.items() if v)
    mapimg = f'<div class="mapbox"><img src="{d["map"]}"></div>' if d.get("map") else ""
    p3 = (f'<div class="slide"><div class="pad">{top(3)}<div class="pill">단지 위치</div>'
          f'<div class="h1" style="font-size:56px">{d["name_l1"]} {d["name_l2"]}</div>'
          f'<div class="walk">{walk}</div>{mapimg}'
          f'<div class="foot" style="margin-top:14px">지도 © NAVER · 핀=단지 위치(지번 기준)</div></div></div>')
    return f"<!DOCTYPE html><html><head><meta charset=utf-8><style>{_css(t)}</style></head><body>{p1}{p2}{p3}</body></html>"


async def render_cards(d: dict, theme: dict, out_dir: Path, stem: str) -> list[Path]:
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        pg = await b.new_page(viewport={"width": 1080, "height": 1080}, device_scale_factor=1)
        await pg.set_content(_html(d, theme), wait_until="networkidle")
        for i, s in enumerate(await pg.query_selector_all(".slide"), 1):
            fp = out_dir / f"{stem}_{i}.png"
            await s.screenshot(path=str(fp)); paths.append(fp)
        await b.close()
    return paths
