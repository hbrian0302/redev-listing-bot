import caption as C


FACTS = {
    "name": "포레나더샵 인천시청역",
    "region": "인천 남동구",
    "bunyang": 6.46,
    "sise": 5.38,
    "margin": -1.08,
    "rcept_bgn": "2026-07-21",
    "rcept_end": "2026-07-21",
    "days_left": 2,
    "movein": "2029.09",
    "decision": "촉수엄금!",
}


def test_허용된_금액만_쓰면_위반없음():
    text = "분양가 6.46억인데 옆 신축이 5.38억이더라고. 1.08억 차이."
    assert C.violations(text, FACTS) == []


def test_없는_금액이_등장하면_잡아낸다():
    """스펙 샘플에 실수로 들어갔던 '현금 3억'이 정확히 이 케이스다."""
    text = "현금 3억 정도는 있어야 해."
    assert C.violations(text, FACTS) == ["3억"]


def test_반올림된_표현도_허용한다():
    """6.46억을 '6억'이라 쓰는 건 허용(소수점 절사는 날조가 아님)."""
    text = "분양가가 6억대야."
    assert C.violations(text, FACTS) == []


def test_없는_날짜가_등장하면_잡아낸다():
    text = "접수는 7월 25일이야."
    assert "7월 25일" in C.violations(text, FACTS)


def test_허용된_날짜는_통과():
    text = "접수는 7월 21일 하루야."
    assert C.violations(text, FACTS) == []


def test_여러_위반을_모두_보고한다():
    text = "현금 3억 있어야 하고 접수는 7월 25일이야."
    v = C.violations(text, FACTS)
    assert "3억" in v and "7월 25일" in v


def test_금액이_없는_문장은_통과():
    text = "여러분~ 이건 좀 아쉬운 것 같아."
    assert C.violations(text, FACTS) == []


def test_build_facts는_파이프라인_값을_모은다():
    data = {"name_l1": "평택", "name_l2": "고덕 우미 린",
            "sub": "경기 평택시 · 무순위 · 입주 2028.12",
            "bunyang": 5.53, "sise": 5.90, "decision": "애매한 가격대"}
    dec = {"margin": 0.37}
    sch = {"rcept_bgn": "2026-07-25", "rcept_end": "2026-07-25"}
    f = C.build_facts(data, dec, sch, days_left=3)
    assert f["name"] == "평택 고덕 우미 린"
    assert f["bunyang"] == 5.53
    assert f["days_left"] == 3
    assert f["rcept_end"] == "2026-07-25"


def test_만원_단위_날조를_잡는다():
    """'현금 3억'을 '5000만원'으로 바꿔 쓰면 뚫리던 구멍."""
    assert C.violations("5000만원만 있으면 돼.", FACTS) == ["5000만원"]


def test_억만원_복합표기의_참값은_통과():
    """6.46억을 '6억 4600만원'으로 쓴 것은 같은 값이다."""
    assert C.violations("분양가 6억 4600만원이야.", FACTS) == []


def test_억만원_복합표기의_날조를_잡는다():
    """억 자리만 맞고 만원 꼬리를 지어낸 경우."""
    v = C.violations("분양가 6억 9900만원이야.", FACTS)
    assert v == ["6억 9900만원"]


def test_만_명은_금액으로_오탐하지_않는다():
    """'30만 명'은 돈이 아니다. '원'이 없으면 금액으로 보지 않는다."""
    assert C.violations("30만 명이 몰렸대.", FACTS) == []


def test_남은일수_날조를_잡는다():
    """days_left=2인데 5일이라 쓰면 독자가 마감을 놓친다."""
    assert C.violations("마감까지 5일 남았어.", FACTS) == ["D-5"]


def test_정확한_남은일수는_통과():
    assert C.violations("접수 얼마 안 남았어. D-2야.", FACTS) == []
    assert C.violations("2일 뒤가 마감이야.", FACTS) == []


def test_날짜의_일은_남은일수로_오탐하지_않는다():
    """'7월 21일 하루야'의 '21일'이 D-21로 잡히면 안 된다."""
    assert C.violations("접수는 7월 21일 하루야.", FACTS) == []


def test_days_left가_없으면_일수검사를_건너뛴다():
    f = dict(FACTS); f["days_left"] = None
    assert C.violations("마감까지 5일 남았어.", f) == []
