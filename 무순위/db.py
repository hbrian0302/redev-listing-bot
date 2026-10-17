#!/usr/bin/env python3
"""무순위 전체 CSV DB — 분석된 전건을 listing_id 기준으로 누적 upsert.

발행 여부와 무관하게 마진 계산에 성공한 모든 건이 들어간다. 삭제는 없다.
Excel 한글 호환을 위해 utf-8-sig로 쓴다.
"""
from __future__ import annotations
import csv, datetime, os
from pathlib import Path

BASE = Path(__file__).resolve().parent
CSV_PATH = BASE / "무순위_전체.csv"

COLUMNS = [
    # 식별
    "listing_id", "단지명", "지역", "주소", "원문URL",
    # 일정
    "공고일", "접수시작", "접수마감", "입주예정",
    # 가격
    "분양가", "시세", "마진", "할인율%", "시세기준", "표본수", "신뢰도",
    # 판정
    "tier", "결정어", "라우팅",
    # 입지
    "입지점수", "등급", "세대수",
    # 메타
    "수집일시", "발행일시",
]


def load(path=None) -> dict[str, dict]:
    """CSV 전체를 listing_id 키 dict으로. 파일 없으면 빈 dict."""
    path = Path(path or CSV_PATH)
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        return {r["listing_id"]: r for r in csv.DictReader(f) if r.get("listing_id")}


def _tmp_path(path: Path) -> Path:
    """프로세스별 임시 파일 경로. 동시 실행 시 서로의 tmp를 지우지 않게 한다.

    파일 잠금은 아니다 — 크래시(FileNotFoundError)는 막지만, 두 프로세스가
    겹쳐 쓰면 나중에 replace()하는 쪽이 앞선 쓰기를 논리적으로 덮어쓸 수 있다.
    완전한 동시성 보호가 필요하면 별도의 파일 잠금이 있어야 한다(이번 범위 밖).
    """
    return path.with_suffix(f"{path.suffix}.{os.getpid()}.tmp")


def upsert(row: dict, path=None) -> None:
    """listing_id 기준으로 갱신 또는 추가하고 전체를 다시 쓴다."""
    lid = str(row.get("listing_id") or "").strip()
    if not lid:
        raise ValueError("listing_id 없는 행은 기록할 수 없다")
    path = Path(path or CSV_PATH)
    rows = load(path)
    merged = rows.get(lid, {})
    merged.update({k: v for k, v in row.items() if k in COLUMNS})
    merged["listing_id"] = lid
    rows[lid] = merged
    tmp = _tmp_path(path)
    with tmp.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        for _lid, r in sorted(rows.items()):
            w.writerow({c: r.get(c, "") for c in COLUMNS})
    tmp.replace(path)


def to_row(pub: dict, data: dict, dec: dict, sch: dict,
           confidence: str, nsample: int, dest: str) -> dict:
    """파이프라인 값들 → CSV 한 행."""
    sub = data.get("sub") or ""
    region = sub.split(" · ")[0] if " · " in sub else sub
    movein = sub.split("입주 ")[-1] if "입주 " in sub else ""
    row = {
        "listing_id": str(pub.get("HOUSE_MANAGE_NO", "")),
        "단지명": pub.get("HOUSE_NM", ""),
        "지역": region,
        "주소": pub.get("HSSPLY_ADRES", ""),
        "원문URL": sch.get("url") or "",
        "공고일": sch.get("pblanc_de") or "",
        "접수시작": sch.get("rcept_bgn") or "",
        "접수마감": sch.get("rcept_end") or "",
        "입주예정": movein,
        "분양가": data.get("bunyang"),
        "시세": data.get("sise"),
        "마진": round(dec.get("margin", 0), 2),
        "할인율%": round(dec.get("cheap_pct", 0), 2),
        "시세기준": data.get("basis", ""),
        "표본수": nsample,
        "신뢰도": confidence,
        "tier": dec.get("tier"),
        "결정어": data.get("decision", ""),
        "라우팅": dest,
        "입지점수": data.get("total"),
        "등급": data.get("grade", ""),
        "세대수": sch.get("supply"),
        "수집일시": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "발행일시": "",
    }
    # 값을 모르는 컬럼은 키를 아예 빼서, upsert 병합이 기존 값을 보존하게 한다.
    # 0은 유효한 값이므로(tier 0 = 촉수엄금!) truthy 검사를 쓰면 안 된다.
    return {k: v for k, v in row.items() if v is not None and v != ""}
