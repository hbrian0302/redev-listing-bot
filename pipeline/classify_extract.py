#!/usr/bin/env python3
"""블로그 본문 → (매물글? 단일?) 판별 + 9필드 추출. 출력 JSON."""
from __future__ import annotations
import json, re, sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm import ask_claude

EXTRACT_PROMPT = """다음은 재개발 부동산 중개사의 네이버 블로그 글이다.
아래 스키마의 **JSON만** 출력하라(코드펜스·설명 금지).

판별:
- is_listing: 이 글이 '매물(특정 물건) 소개' 글이면 true. 시황·잡담·일반정보면 false.
- is_single: 매물이 정확히 1개면 true. 2개 이상이거나 불명확하면 false.
- is_redev_sale: 이 매물이 **재개발·재건축 정비사업 물건의 매매**(입주권/조합원 분양권/정비구역 내 빌라·주택·대지 매매)이면 true.
  **전세·월세·반전세** 임대이거나, **정비사업과 무관한 일반 아파트/오피스텔/상가/분양권** 매물이면 false.
(위 셋 중 하나라도 false면 나머지 필드는 null로 둬도 된다.)

추출(글에 있는 값만, 없으면 null — 지어내지 마라):
- zone(구역명), stage(진행단계), location(위치 구·동),
  transit(교통 — 반드시 "○호선 ○○역 도보 ○분" 형식으로 역명 포함. 역명 불명이면 null),
  price(매매가), premium(프리미엄), rights_value(권리가액, null 가능),
  expected_movein(예상입주, null 가능), area(전용면적/평형, null 가능),
  intro_text(중개사가 쓴 매물 소개 문단 원문 그대로, 최대 500자)

JSON 스키마:
{"is_listing":bool,"is_single":bool,"is_redev_sale":bool,"zone":str|null,"stage":str|null,"location":str|null,
"transit":str|null,"price":str|null,"premium":str|null,"rights_value":str|null,
"expected_movein":str|null,"area":str|null,"intro_text":str|null}

[블로그 글]
"""


def parse_llm_json(text: Optional[str]) -> Optional[dict]:
    if not text:
        return None
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t).strip()
    m = re.search(r"\{.*\}", t, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def extract(content: str) -> dict:
    """본문 → 추출 dict. 매물글 아니거나 파싱 실패 시 is_listing=False 보장."""
    raw = ask_claude(EXTRACT_PROMPT + content[:3000], model="sonnet")
    parsed = parse_llm_json(raw)
    if parsed is None:
        return {"is_listing": False, "is_single": False, "reason": "parse_failed"}
    return parsed


if __name__ == "__main__":
    txt = Path(sys.argv[1]).read_text()
    print(json.dumps(extract(txt), ensure_ascii=False, indent=2))
