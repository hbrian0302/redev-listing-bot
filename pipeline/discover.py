#!/usr/bin/env python3
"""하루 1회: 제휴 블로그 크롤 → 신규 매물글 → 카드 생성 큐 적재.

사용:
  uv run --with jinja2 python discover.py --baseline   # 첫 실행: 현재 글 전부 seen 처리(카드X)
  uv run --with jinja2 python discover.py              # 이후: 새 글만 처리
"""
from __future__ import annotations
import asyncio, csv, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import DB
from crawler import fetch_post_meta, fetch_content
from classify_extract import extract
from generate import make_card

BASE = Path(__file__).resolve().parent
SOURCES = BASE / "sources.json"
# 데이터레이어(매물 카드뉴스)의 정제 중개사 명단을 단일 출처로 사용. 없으면 sources.json 폴백.
BROKER_CSV = BASE.parent / "매물 카드뉴스" / "data" / "중개사_소스.csv"


def parse_broker_csv(path) -> list:
    """중개사_소스.csv(utf-8-sig) → 상태=active 행만 [{blog_id, name, phone}].
    phone은 전화_유효=Y인 경우에만 값, 아니면 빈 문자열."""
    blogs = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if (row.get("상태") or "").strip() == "active":
                bid = (row.get("블로그ID") or "").strip()
                if bid:
                    phone = (row.get("전화번호") or "").strip() if (row.get("전화_유효") or "").strip() == "Y" else ""
                    blogs.append({"blog_id": bid, "name": (row.get("중개사명") or bid).strip(), "phone": phone})
    return blogs


def load_blogs():
    """제휴 중개사 명단. 중개사_소스.csv(active) 우선, 없거나 비면 sources.json 폴백."""
    if BROKER_CSV.exists():
        blogs = parse_broker_csv(BROKER_CSV)
        if blogs:
            return blogs
    return json.loads(SOURCES.read_text())["blogs"]


async def run(baseline: bool = False):
    db = DB()
    blogs = load_blogs()
    print(f"● discover 시작 (baseline={baseline}, 블로그 {len(blogs)}개)")
    for b in blogs:
        bid, bname = b["blog_id"], b.get("name", b["blog_id"])
        try:
            metas = fetch_post_meta(bid)
        except Exception as e:
            print(f"  ! {bid} 목록 실패: {e}"); continue
        new = [m for m in metas if not db.is_seen(bid, m["log_no"])]
        print(f"  {bname}: 전체 {len(metas)}, 신규 {len(new)}")
        for m in new:
            log_no = m["log_no"]
            if baseline:
                db.mark_seen(bid, log_no, url="", status="baseline"); continue
            try:
                art = await fetch_content(bid, log_no)
                # 일시적 실패(네트워크/타임아웃/빈 로드)는 기록하지 않고 다음 실행에서 재시도
                if not art or not art["content"]:
                    print(f"    retry-later {log_no} (본문 수집 실패/빈 글)")
                    continue
                ex = extract(art["content"])
                if ex.get("reason") == "parse_failed":
                    # LLM 일시 오류 — 영구 skip 금지, 다음 실행 재시도
                    print(f"    retry-later {log_no} (LLM 파싱 실패)")
                    continue
                url = art["url"]
                if not ex.get("is_listing") or not ex.get("is_single"):
                    db.record_skip(bid, log_no, url,
                                   "not_listing" if not ex.get("is_listing") else "multi_or_unclear")
                    print(f"    skip {log_no} ({'비매물' if not ex.get('is_listing') else '다중/불명'})")
                    continue
                if not ex.get("is_redev_sale"):
                    db.record_skip(bid, log_no, url, "not_redev_sale")
                    print(f"    skip {log_no} (전세/월세·비재개발 매물)")
                    continue
                if not ex.get("zone") or not ex.get("price"):
                    db.record_skip(bid, log_no, url, "incomplete")
                    print(f"    skip {log_no} (필수필드 누락: zone/price)")
                    continue
                listing = {k: ex.get(k) for k in
                           ("zone", "stage", "location", "transit", "price", "premium",
                            "rights_value", "expected_movein", "area")}
                listing["source_name"] = bname
                listing["source_phone"] = b.get("phone", "")   # 전화_유효=Y인 중개사만 값
                listing["source_url"] = url
                listing["intro_text"] = ex.get("intro_text") or art["content"][:500]
                lid = db.record_listing(bid, log_no, url, listing["intro_text"], listing)
                listing["listing_id"] = lid
                await make_card(listing, enqueue=True)
                print(f"    ✅ 카드 생성: {log_no} (listing {lid})")
            except Exception as e:
                # 한 글의 실패가 블로그 전체를 멈추지 않게 — 기록 안 함(다음 실행 재시도)
                print(f"    ! {log_no} 처리 실패(재시도 예정): {e}")
                continue
    print("● discover 종료")


if __name__ == "__main__":
    asyncio.run(run(baseline="--baseline" in sys.argv[1:]))
