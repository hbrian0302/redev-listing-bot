#!/usr/bin/env python3
"""매일 12시: 수도권 무순위 신규 공고 → 마진·입지점수 분석 → 다크 3장 카드 → 검수큐.
사용:
  python pipeline.py --baseline    # 현재 공고 전부 seen 처리(카드 생성 X) — 최초 1회
  python pipeline.py               # 신규 공고만 분석·카드생성
  python pipeline.py --test 2      # seen 무시하고 최근 2건 생성(검증용, seen 갱신 X)
"""
from __future__ import annotations
import sys, json, re, asyncio, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import datagokr, geo, margin as M, score as SC, themes as TH
from render import render_cards

BASE = Path(__file__).resolve().parent
Q = BASE / "queue" / "pending"; Q.mkdir(parents=True, exist_ok=True)
SEEN = BASE / "seen.json"


def load_seen() -> set:
    return set(json.loads(SEEN.read_text())) if SEEN.exists() else set()

def save_seen(s: set):
    SEEN.write_text(json.dumps(sorted(s), ensure_ascii=False))

def recent_months(n=4) -> list[str]:
    d = datetime.date.today().replace(day=1)
    out = []
    for _ in range(n):
        out.append(d.strftime("%Y%m")); d = (d - datetime.timedelta(days=1)).replace(day=1)
    return out

def split_name(house_nm: str) -> tuple[str, str]:
    nm = re.sub(r"\s*\([^)]*\)\s*$", "", house_nm or "").strip()
    parts = nm.split(" ", 1)
    return (parts[0], parts[1]) if len(parts) == 2 else (nm, "")


async def process_one(pub: dict, seq: int) -> dict | None:
    mno = pub["HOUSE_MANAGE_NO"]; house = pub.get("HOUSE_NM", "")
    models = datagokr.musunwi_models(mno)
    if not models:
        print(f"  skip {mno} (주택형 없음)"); return None
    priced = [(int(m["LTTOT_TOP_AMOUNT"]) / 10000, m) for m in models if str(m.get("LTTOT_TOP_AMOUNT", "")).isdigit()]
    if not priced:
        print(f"  skip {mno} (분양가 없음)"); return None
    bunyang, rep = min(priced, key=lambda x: x[0])
    target_ar = float(rep["HOUSE_TY"][:6])
    addr = pub.get("HSSPLY_ADRES", ""); lawd = datagokr.resolve_lawd(addr)
    if not lawd:
        print(f"  skip {mno} (LAWD 미해석: {addr[:20]})"); return None
    movein = pub.get("MVN_PREARNGE_YM", ""); movein_year = int(movein[:4]) if movein[:4].isdigit() else None
    coord, dong = geo.geocode_dong(addr)
    sise, basis, nsample = M.market_price(house, target_ar, lawd, recent_months(), movein_year or 9999, dong)
    if sise is None:
        print(f"  skip {mno} (시세 없음)"); return None
    conf = M.confidence(nsample)
    dec = M.decide(bunyang, sise)
    poi = {}; mapuri = None
    walk = {}
    if coord:
        poi = geo.nearest_poi(*coord)
        mapuri = geo.static_map_datauri(*coord)
        if poi.get("역"): walk["최근접역"] = f'{poi["역"][0]} {poi["역"][1]}분'
        if poi.get("초등"): walk["초등"] = f'{poi["초등"][0]} {poi["초등"][1]}분'
        if poi.get("공원"): walk["공원"] = f'{poi["공원"][0]} {poi["공원"][1]}분'
    total_supply = datagokr.original_total_supply(house)
    scr = SC.score(house, movein_year, total_supply, poi)
    l1, l2 = split_name(house)
    region = f'{pub.get("SUBSCRPT_AREA_CODE_NM","")} {addr.split()[1] if len(addr.split())>1 else ""}'.strip()
    data = {
        "name_l1": l1, "name_l2": l2,
        "sub": f'{region} · {pub.get("HOUSE_SECD_NM","무순위")} · 입주 {movein[:4]}.{movein[4:]}' if movein else region,
        "bunyang": round(bunyang, 2), "sise": sise, "basis": basis,
        "decision": dec["decision"], "mean": dec["mean"], "tail": dec["tail"],
        "sc": scr["sc"], "total": scr["total"], "grade": scr["grade"],
        "walk": walk, "map": mapuri,
    }
    data["confidence"] = conf; data["nsample"] = nsample
    theme = TH.theme_for(seq)
    paths = await render_cards(data, theme, Q, mno)
    cheap = dec["cheap_pct"]
    conf_note = "" if conf == "ok" else f'\n⚠️ 실거래 표본 {nsample}건 — 신뢰도 낮음, 판정 참고만'
    caption = (f'[무순위 살까말까] {l1} {l2} → {dec["decision"]}\n'
               f'{data["sub"]}\n'
               f'분양가 {bunyang:.2f}억 vs 인근 신축 {sise:.2f}억 → {"비쌈" if dec["gap"]>0 else "쌈"} {abs(cheap):.0f}%\n'
               f'입지 {scr["total"]}점 {scr["grade"]}등급 (브역대신평공초)\n\n'
               f'{dec["mean"]}. {dec["tail"]}\n\n'
               f'※ 분양가=공고 기준(옵션·확장 별도), 시세=최근 실거래(시점차 있음). 참고용.{conf_note}\n'
               f'내 관심 줍줍 이득인지 → 텔레그램 @your_handle')
    data.pop("map", None)  # 대용량 base64는 json에서 제외
    rec = {"listing_id": mno, "house_nm": house, "images": [str(p) for p in paths],
           "caption": caption, "theme": theme["key"], "data": data}
    (Q / f"{mno}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2))
    print(f"  ✅ {mno} {l1} {l2} → {dec['decision']} (시세 {sise}억 {basis[:20]}·표본{nsample}/{conf}) / 입지 {scr['total']}점 [{theme['key']}]")
    return rec


async def main():
    args = sys.argv[1:]
    pubs = datagokr.musunwi_list()
    pubs.sort(key=lambda r: r.get("RCRIT_PBLANC_DE") or "", reverse=True)
    if "--baseline" in args:
        seen = {p["HOUSE_MANAGE_NO"] for p in pubs}
        save_seen(seen); print(f"baseline: {len(seen)}건 seen 처리(카드 생성 안 함)"); return
    if "--test" in args:
        n = int(args[args.index("--test") + 1])
        print(f"[test] 최근 {n}건 생성:")
        for i, p in enumerate(pubs[:n]):
            await process_one(p, i)
        return
    seen = load_seen()
    new = [p for p in pubs if p["HOUSE_MANAGE_NO"] not in seen]
    print(f"수도권 무순위 {len(pubs)}건 중 신규 {len(new)}건")
    for i, p in enumerate(new):
        try:
            await process_one(p, len(seen) + i)
        except Exception as e:
            print(f"  ! {p.get('HOUSE_MANAGE_NO')} 실패: {e}")
        seen.add(p["HOUSE_MANAGE_NO"])
    save_seen(seen)


if __name__ == "__main__":
    asyncio.run(main())
