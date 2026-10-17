import csv
import db


def _read(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def test_첫_upsert가_헤더와_행을_만든다(tmp_path):
    p = tmp_path / "t.csv"
    db.upsert({"listing_id": "1", "단지명": "가나아파트"}, path=p)
    rows = _read(p)
    assert len(rows) == 1
    assert rows[0]["listing_id"] == "1"
    assert rows[0]["단지명"] == "가나아파트"


def test_같은_id는_중복되지_않고_갱신된다(tmp_path):
    p = tmp_path / "t.csv"
    db.upsert({"listing_id": "1", "단지명": "옛이름", "마진": "0.5"}, path=p)
    db.upsert({"listing_id": "1", "단지명": "새이름", "마진": "1.8"}, path=p)
    rows = _read(p)
    assert len(rows) == 1
    assert rows[0]["단지명"] == "새이름"
    assert rows[0]["마진"] == "1.8"


def test_다른_id는_함께_보존된다(tmp_path):
    p = tmp_path / "t.csv"
    db.upsert({"listing_id": "1", "단지명": "가"}, path=p)
    db.upsert({"listing_id": "2", "단지명": "나"}, path=p)
    db.upsert({"listing_id": "1", "단지명": "가수정"}, path=p)
    rows = _read(p)
    assert len(rows) == 2
    by_id = {r["listing_id"]: r for r in rows}
    assert by_id["1"]["단지명"] == "가수정"
    assert by_id["2"]["단지명"] == "나"


def test_빠진_컬럼은_빈문자열(tmp_path):
    p = tmp_path / "t.csv"
    db.upsert({"listing_id": "1"}, path=p)
    rows = _read(p)
    assert rows[0]["마진"] == ""


def test_컬럼_순서가_고정되어_있다(tmp_path):
    p = tmp_path / "t.csv"
    db.upsert({"listing_id": "1"}, path=p)
    with open(p, encoding="utf-8-sig") as f:
        header = f.readline().strip().split(",")
    assert header == db.COLUMNS
    assert header[0] == "listing_id"


def test_listing_id_없으면_거부(tmp_path):
    import pytest
    p = tmp_path / "t.csv"
    with pytest.raises(ValueError):
        db.upsert({"단지명": "가"}, path=p)


def test_load는_id로_키잉된_dict을_준다(tmp_path):
    p = tmp_path / "t.csv"
    db.upsert({"listing_id": "1", "단지명": "가"}, path=p)
    db.upsert({"listing_id": "2", "단지명": "나"}, path=p)
    loaded = db.load(path=p)
    assert set(loaded) == {"1", "2"}
    assert loaded["2"]["단지명"] == "나"


def test_파일이_없으면_load는_빈dict(tmp_path):
    assert db.load(path=tmp_path / "없음.csv") == {}


def test_to_row가_파이프라인_값을_컬럼으로_옮긴다():
    pub = {"HOUSE_MANAGE_NO": "2026910185", "HOUSE_NM": "포레나더샵 인천시청역(2차)",
           "HSSPLY_ADRES": "인천광역시 남동구 간석1동 311-1번지 일원",
           "SUBSCRPT_AREA_CODE_NM": "인천"}
    data = {"sub": "인천 남동구 · 무순위 · 입주 2029.09", "bunyang": 6.46, "sise": 5.38,
            "basis": "시군구 신축 유사평형 중위(8건·광역참고)", "decision": "촉수엄금!",
            "total": 83, "grade": "A"}
    dec = {"margin": -1.08, "cheap_pct": -20.07, "tier": 0}
    sch = {"pblanc_de": "2026-07-16", "rcept_bgn": "2026-07-21",
           "rcept_end": "2026-07-21", "supply": 10, "url": "https://x"}
    r = db.to_row(pub, data, dec, sch, confidence="ok", nsample=8, dest="blog_pool")
    assert r["listing_id"] == "2026910185"
    assert r["단지명"] == "포레나더샵 인천시청역(2차)"
    assert r["마진"] == -1.08
    assert r["tier"] == 0
    assert r["라우팅"] == "blog_pool"
    assert r["접수마감"] == "2026-07-21"
    assert r["세대수"] == 10
    assert r["수집일시"]


def test_to_row는_모르는_값의_키를_생략한다():
    """빈 값 키를 남기면 upsert 병합이 기존 값을 덮어버린다."""
    pub = {"HOUSE_MANAGE_NO": "1", "HOUSE_NM": "가나"}
    data = {"sub": "인천 남동구 · 무순위", "bunyang": 6.46, "sise": 5.38,
            "decision": "촉수엄금!"}          # total·grade 없음(백필 시나리오)
    dec = {"margin": -1.08, "cheap_pct": -20.07, "tier": 0}
    sch = {"rcept_end": "2026-07-21"}
    r = db.to_row(pub, data, dec, sch, confidence="ok", nsample=8, dest="blog_pool")
    assert "발행일시" not in r
    assert "입지점수" not in r
    assert "등급" not in r


def test_to_row는_0을_유효값으로_살린다():
    """tier 0(촉수엄금!)은 정상 값이다. truthy 검사로 거르면 안 된다."""
    pub = {"HOUSE_MANAGE_NO": "1"}
    data = {"sub": "인천", "total": 0}
    dec = {"margin": 0, "cheap_pct": 0, "tier": 0}
    sch = {}
    r = db.to_row(pub, data, dec, sch, confidence="ok", nsample=0, dest="blog_pool")
    assert r["tier"] == 0
    assert r["마진"] == 0
    assert r["표본수"] == 0
    assert r["입지점수"] == 0


def test_재분석이_발행일시를_지우지_않는다(tmp_path):
    """to_row 결과로 재-upsert해도 다른 경로가 채운 값이 보존돼야 한다."""
    p = tmp_path / "t.csv"
    pub = {"HOUSE_MANAGE_NO": "1", "HOUSE_NM": "가나"}
    data = {"sub": "인천", "bunyang": 6.0, "sise": 7.6, "total": 83, "grade": "A"}
    dec = {"margin": 1.6, "cheap_pct": 21.05, "tier": 3}
    sch = {"rcept_end": "2026-07-21"}
    db.upsert(db.to_row(pub, data, dec, sch, "ok", 8, "pending"), path=p)
    db.upsert({"listing_id": "1", "발행일시": "2026-07-20 19:00:00"}, path=p)

    # 입지점수를 못 채우는 백필 경로가 같은 건을 재분석
    thin = {"sub": "인천", "bunyang": 6.0, "sise": 7.6}
    db.upsert(db.to_row(pub, thin, dec, sch, "ok", 8, "pending"), path=p)

    row = db.load(path=p)["1"]
    assert row["발행일시"] == "2026-07-20 19:00:00"
    assert row["입지점수"] == "83"
    assert row["등급"] == "A"


def test_tmp파일명이_프로세스마다_다르다(tmp_path):
    """같은 tmp 이름을 쓰면 동시 실행 시 한쪽이 FileNotFoundError로 죽는다."""
    import os
    p = tmp_path / "t.csv"
    db.upsert({"listing_id": "1"}, path=p)
    assert str(os.getpid()) in db._tmp_path(p).name
    assert db._tmp_path(p).name.endswith(".tmp")
