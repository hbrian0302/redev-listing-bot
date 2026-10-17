import datetime
import publish as PUB

TODAY = datetime.date(2026, 7, 20)


def test_마감_임박순으로_정렬된다():
    items = [
        {"stem": "a", "rcept_end": "2026-07-30"},
        {"stem": "b", "rcept_end": "2026-07-21"},
        {"stem": "c", "rcept_end": "2026-07-25"},
    ]
    out = PUB.sort_by_deadline(items, today=TODAY)
    assert [i["stem"] for i in out] == ["b", "c", "a"]


def test_마감일_없는_건은_뒤로_밀린다():
    items = [
        {"stem": "none", "rcept_end": None},
        {"stem": "soon", "rcept_end": "2026-07-21"},
    ]
    out = PUB.sort_by_deadline(items, today=TODAY)
    assert [i["stem"] for i in out] == ["soon", "none"]


def test_만료된_건은_판정된다():
    assert PUB.is_expired({"rcept_end": "2026-07-19"}, today=TODAY) is True


def test_오늘_마감은_아직_유효():
    assert PUB.is_expired({"rcept_end": "2026-07-20"}, today=TODAY) is False


def test_마감일_없으면_만료로_보지_않는다():
    assert PUB.is_expired({"rcept_end": None}, today=TODAY) is False


def test_만료건은_정렬결과에서_제외된다():
    items = [
        {"stem": "dead", "rcept_end": "2026-07-10"},
        {"stem": "alive", "rcept_end": "2026-07-25"},
    ]
    out = PUB.sort_by_deadline(items, today=TODAY, drop_expired=True)
    assert [i["stem"] for i in out] == ["alive"]
