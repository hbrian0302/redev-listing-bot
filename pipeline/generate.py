#!/usr/bin/env python3
"""매물 데이터 → fighter_note·캡션 생성 + 카드 렌더 + 검수 큐 적재.

사용: uv run --with jinja2 python generate.py <listing.json> [--enqueue]
listing.json: classify_extract가 뱉은 9필드 + intro_text + listing_id + url 포함.
"""
from __future__ import annotations
import asyncio, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm import ask_claude
from render import render_card
from schema import build_caption, decide_layout
from mapgen import static_map_datauri

BASE = Path(__file__).resolve().parent
PENDING = BASE / "queue" / "pending"


def build_note_prompt(zone: str, stage: str, intro_text: str) -> str:
    """중개사 소개글 → 큐레이터 톤 한줄평 변환 프롬프트(가드레일 내장)."""
    return (
        "너는 정보 큐레이터 페르소나의 카피라이터다. 아래 중개사 소개글을 근거로,\n"
        f"'{zone} ({stage})' 매물의 **한 줄 코멘트**를 쓴다.\n\n"
        "[엄수 규칙 — 가드레일]\n"
        "1. 소개글에 있는 사실(위치·단계·가격 근거)만 사용. **없는 수치·효능을 지어내지 마라**(환각 금지).\n"
        "2. 소개글의 영업성 단정('무조건 오른다/마지막 기회/확정 수익' 등)은 그대로 옮기지 말고 **중립화**하라"
        "(예: '입지가 좋다는 평'처럼 의견·관점으로). 확정수익·단정 시세예측 금지.\n"
        "3. 개인(조합장 등 자연인) 실명이 있으면 'XXX'로 마스킹. 구역·단지·조합명은 그대로 둬도 된다.\n"
        "4. '추천/사세요'가 아니라 '이런 라인이다'는 정보·관점 톤.\n"
        "5. 출력은 **한 줄(최대 45자)** 본문만. 따옴표·설명·이모지 금지.\n\n"
        f"[중개사 소개글]\n{intro_text}\n"
    )


def build_detail_prompt(zone: str, stage: str, intro_text: str) -> str:
    """중개사 소개글 → 세부 설명 3줄(한줄평 아래 작은 글씨). 가드레일 내장."""
    return (
        "너는 정보 큐레이터 페르소나의 카피라이터다. 아래 중개사 소개글을 근거로,\n"
        f"'{zone} ({stage})' 매물의 **세부 설명을 정확히 3줄**로 쓴다(한줄평 아래 작은 글씨로 들어감).\n\n"
        "[엄수 규칙 — 가드레일]\n"
        "1. 소개글에 있는 사실만 사용. 없는 수치·효능을 지어내지 마라(환각 금지).\n"
        "2. 영업성 단정('무조건/마지막 기회/확정 수익')은 중립화. 확정 시세예측 금지.\n"
        "3. 개인(자연인) 실명은 'XXX' 마스킹. 구역·단지·조합명은 그대로 둬도 된다.\n"
        "4. 위치·진행단계·자금(종잣돈/투자 규모)·입지 강점·유의점 중심으로 담백하게.\n"
        "5. 출력은 **정확히 3줄**(각 줄 짧게, 줄바꿈으로 구분). 따옴표·설명·이모지·머리기호 금지.\n\n"
        f"[중개사 소개글]\n{intro_text}\n"
    )


async def make_card(listing: dict, enqueue: bool = False) -> dict:
    listing = dict(listing)          # 호출자 dict 변조 방지
    intro = listing.get("intro_text", "")
    note = ask_claude(build_note_prompt(listing["zone"], listing["stage"], intro), model="sonnet")
    listing["fighter_note"] = (note or "").strip().strip('"') or "정보제공용 매물 — 본인 판단 필요"
    detail = ask_claude(build_detail_prompt(listing["zone"], listing["stage"], intro), model="sonnet")
    listing["detail"] = (detail or "").strip()
    # 네이버 지도(핀) — 실패/키없음 시 None → 슬라이드3 placeholder로 폴백
    listing["map_img"] = static_map_datauri(listing.get("location") or listing.get("zone", ""))
    stem = str(listing.get("listing_id") or listing.get("log_no") or "card")
    paths = await render_card(listing, PENDING, stem)
    caption = build_caption(listing)
    draft = {
        "listing_id": listing.get("listing_id"),
        "layout": decide_layout(listing),
        "images": [str(p) for p in paths],
        "caption": caption,
        # map_img는 대용량 base64라 JSON 저장에서 제외(이미 PNG로 렌더됨)
        "data": {k: v for k, v in listing.items() if k != "map_img"},
        "url": listing.get("source_url", ""),
    }
    if enqueue:
        (PENDING / f"{stem}.json").write_text(json.dumps(draft, ensure_ascii=False, indent=2))
        print(f"→ 검수 큐 적재: {stem} ({draft['layout']}, {len(paths)}장)")
    return draft


async def main():
    args = sys.argv[1:]
    path = next(a for a in args if not a.startswith("--"))
    listing = json.loads(Path(path).read_text())
    draft = await make_card(listing, enqueue="--enqueue" in args)
    print(json.dumps({k: draft[k] for k in ("layout", "images", "caption")},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
