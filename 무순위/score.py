"""브역대신평공초 입지 100점 채점. 브15 역15 대15 신15 평15 공10 초15.
기준: blog.naver.com/princesshouse + 공원. 역·초·공원=OSM 실거리(geo.nearest_poi)."""
from __future__ import annotations

BRAND_1GUN = ["자이", "래미안", "힐스테이트", "푸르지오", "더샵", "포레나", "아이파크",
              "롯데캐슬", "e편한세상", "디에이치", "아크로", "써밋", "트리마제", "꿈에그린",
              "센트레빌", "SK뷰", "sk뷰", "리슈빌", "우미린", "해모로", "스위첸"]
ORDER = ["브", "역", "대", "신", "평", "공", "초"]
LAB = {"브": "브랜드", "역": "역세권", "대": "대단지", "신": "신축", "평": "평지", "공": "공원", "초": "초품아"}
FULL = {"브": 15, "역": 15, "대": 15, "신": 15, "평": 15, "공": 10, "초": 15}


def _band(v, cuts, pts):
    for c, p in zip(cuts, pts):
        if v <= c:
            return p
    return pts[-1]


def score(house_nm: str, movein_year: int | None, total_supply: int | None, poi: dict) -> dict:
    sc = {}
    # 브
    hit = [b for b in BRAND_1GUN if b in (house_nm or "")]
    sc["브"] = (15 if hit else 4, f"1군({'·'.join(hit)})" if hit else "무브랜드")
    # 역
    st = poi.get("역")
    if st:
        w = st[1]; sc["역"] = (_band(w, [5, 10, 15], [15, 11, 7, 3]), f"{st[0]} 도보 {w}분")
    else:
        sc["역"] = (3, "인근 역 없음")
    # 대
    if total_supply:
        p = 15 if total_supply >= 1500 else 12 if total_supply >= 1000 else 8 if total_supply >= 500 else 4
        sc["대"] = (p, f"{total_supply}세대")
    else:
        sc["대"] = (6, "총세대 미확인(보수)")
    # 신
    if movein_year:
        age = movein_year - 2026
        p = 15 if movein_year >= 2021 else 10 if movein_year >= 2016 else 6 if movein_year >= 2006 else 3
        sc["신"] = (p, f"{movein_year} 입주" + ("예정" if age > 0 else ""))
    else:
        sc["신"] = (8, "입주시기 미확인")
    # 평 (수도권 기본 평지)
    sc["평"] = (13, "수도권 평지 가정")
    # 공
    pk = poi.get("공원")
    if pk:
        w = pk[1]; sc["공"] = (_band(w, [5, 10], [10, 6, 3]), f"{pk[0]} 도보 {w}분")
    else:
        sc["공"] = (3, "인근 공원 없음")
    # 초
    el = poi.get("초등")
    if el:
        w = el[1]; sc["초"] = (_band(w, [2, 5, 10], [15, 11, 7, 3]), f"{el[0]} 도보 {w}분")
    else:
        sc["초"] = (3, "인근 초등 없음")
    total = sum(v[0] for v in sc.values())
    grade = "S" if total >= 85 else "A" if total >= 70 else "B" if total >= 55 else "C" if total >= 40 else "D"
    return {"sc": sc, "total": total, "grade": grade}
