"""마진 계산 — 무순위 분양가 vs 인근 시세(동일단지 우선→대장 신축 폴백) + 결정어."""
from __future__ import annotations
import statistics
from datagokr import apt_trades


def _brand_token(house_nm: str) -> str:
    """단지명에서 브랜드 토큰(첫 단어). 역명 오탐 방지용."""
    return (house_nm or "").split("(")[0].split()[0] if house_nm else ""


def recent_trades(lawd5: str, months: list[str]) -> list[dict]:
    out = []
    for ym in months:
        out += apt_trades(lawd5, ym)
    return out


import re
def _norm(s):
    return (s or "").replace(" ", "")

def _norm_dong(s):
    """행정동→법정동 근사: '간석1동'→'간석동' (실거래 umd는 법정동)."""
    return re.sub(r"(\D+)\d+동$", r"\1동", (s or "").strip())

def market_price(house_nm: str, target_ar: float, lawd5: str, months: list[str],
                 movein_year: int, target_dong: str | None = None):
    """(시세억, 기준설명, 표본수). 동일단지→동(법정동) 유사평형 신축→시군구 순, 전부 중위값(최고가 아님)."""
    trades = recent_trades(lawd5, months)
    yr_floor = min(2018, movein_year - 8) if movein_year and movein_year < 9000 else 2018
    band = [t for t in trades if abs(t["ar"] - target_ar) <= 3 and t["year"].isdigit() and int(t["year"]) >= yr_floor]
    if not band:
        band = [t for t in trades if abs(t["ar"] - target_ar) <= 3]
    if not band:
        return None, "인근 유사평형 실거래 없음", 0
    med = lambda ts: round(statistics.median([t["amt"] for t in ts]), 2)
    # 1) 동일단지(입주 단지)
    brand = _brand_token(house_nm)
    same = [t for t in band if brand and brand in t["apt"] and _norm(house_nm.split("(")[0])[:6] in _norm(t["apt"])]
    if movein_year and movein_year <= 2026 and len(same) >= 3:
        return med(same), f"동일단지 실거래 중위({len(same)}건)", len(same)
    # 2) 같은 법정동 유사평형 신축 (진짜 인근)
    if target_dong:
        td = _norm_dong(target_dong)
        coh = [t for t in band if _norm_dong(t.get("umd")) == td]
        if len(coh) >= 3:
            return med(coh), f"{target_dong} 신축 유사평형 중위({len(coh)}건·{len({t['apt'] for t in coh})}단지)", len(coh)
    # 3) 폴백: 시군구 유사평형 신축 중위(광역·최고가 아님)
    return med(band), f"시군구 신축 유사평형 중위({len(band)}건·광역참고)", len(band)


def confidence(n: int) -> str:
    return "ok" if n >= 5 else "low" if n >= 3 else "very_low"


# 피드 단독 게시 컷(억). Task 4 측정 결과로 확정한다.
FEED_CUT = 1.5
# 절대액이 상위 등급이어도 비율이 이 값 미만이면 한 단계 강등(고가 단지 시세 오차 방어)
RATIO_GUARD_PCT = 3.0

_LADDER = {3: "무조건 신청!", 2: "고민해볼만해요", 1: "애매한 가격대", 0: "촉수엄금!"}


def decide(bunyang: float, sise: float) -> dict:
    """분양가 vs 시세 → 결정어·등급·문구.

    등급은 절대 마진(억)으로 매기고 비율은 가드로만 쓴다.
    마진 = sise - bunyang (양수 = 시세보다 싸다).
    """
    cheap = round((sise - bunyang) / sise * 100, 2) if sise else 0
    gap = round(bunyang - sise, 2)
    m = -gap  # 마진(억)

    if m >= FEED_CUT:
        tier = 3
    elif m >= 0.5:
        tier = 2
    elif m > -0.5:
        tier = 1
    else:
        tier = 0

    # 비율 가드: 절대액만 크고 비율이 미미하면 시세 추정 오차일 수 있다
    if tier == 3 and cheap < RATIO_GUARD_PCT:
        tier = 2

    d = _LADDER[tier]
    if gap > 0:
        mean = f"무순위 분양가가 인근 시세보다 {gap:.2f}억 비쌉니다"
        tail = "같은 값이면 옆 신축을 사는 게 유리합니다."
    else:
        mean = f"인근 신축 시세보다 {abs(gap):.2f}억 쌉니다"
        tail = "시세보다 싸게 잡는 안전마진 구간입니다."
    return {"decision": d, "tier": tier, "cheap_pct": cheap,
            "gap": gap, "margin": m, "mean": mean, "tail": tail}


def feed_eligible(tier: int, confidence: str, basis: str | None = None) -> bool:
    """스레드·인스타 피드에 단독 게시할 자격.

    강추(tier 3)만 내보내고, 표본이 너무 적으면(very_low) 막는다.
    시군구 광역 폴백까지 내려간 시세 추정은 오차가 크므로 표본이 넉넉할 때(ok)만 통과시킨다.
    """
    if tier != 3 or confidence == "very_low":
        return False
    if basis and "광역참고" in basis:
        return confidence == "ok"
    return True
