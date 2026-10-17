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
    "basis": "시군구 신축 유사평형 중위(8건·광역참고)",
}

GOOD = """여러분~ 인천시청역 줍줍은 좀 아쉬운 듯.

역세권 신축인 건 맞는데 6.46억이야.
바로 옆 신축이 5.38억에 거래됐더라고.

접수 7월 21일 하루야.

좋아요랑 팔로우 부탁해🙏"""

BAD = "현금 3억은 있어야 해. 접수 7월 25일이야."


def test_생성결과가_검증을_통과하면_그대로_반환():
    calls = []
    def fake_llm(prompt):
        calls.append(prompt)
        return GOOD
    out = C.generate(FACTS, channel="threads", llm=fake_llm)
    assert out == GOOD
    assert len(calls) == 1


def test_날조가_있으면_재시도한다():
    seq = [BAD, GOOD]
    def fake_llm(prompt):
        return seq.pop(0)
    out = C.generate(FACTS, channel="threads", llm=fake_llm)
    assert out == GOOD
    assert seq == []


def test_계속_날조하면_안전템플릿으로_폴백():
    def fake_llm(prompt):
        return BAD
    out = C.generate(FACTS, channel="threads", llm=fake_llm)
    assert C.violations(out, FACTS) == []
    assert "팔로우" in out


def test_폴백_템플릿에도_접수일이_들어간다():
    def fake_llm(prompt):
        return BAD
    out = C.generate(FACTS, channel="threads", llm=fake_llm)
    assert "7월 21일" in out


def test_채널별로_다른_프롬프트를_쓴다():
    seen = []
    def fake_llm(prompt):
        seen.append(prompt)
        return GOOD
    C.generate(FACTS, channel="threads", llm=fake_llm)
    C.generate(FACTS, channel="instagram", llm=fake_llm)
    assert seen[0] != seen[1]
    assert "6~7행" in seen[0]
    assert "12~15행" in seen[1]


def test_프롬프트에_금지사항이_들어간다():
    seen = []
    def fake_llm(prompt):
        seen.append(prompt)
        return GOOD
    C.generate(FACTS, channel="threads", llm=fake_llm)
    p = seen[0]
    assert "브역대신평공초" in p       # 내부약어 금지 명시
    assert "여러분" in p             # 호칭 지정
    assert "텔레그램" in p             # 링크 금지 명시


def test_알수없는_채널은_에러():
    import pytest
    with pytest.raises(ValueError):
        C.generate(FACTS, channel="tiktok", llm=lambda p: GOOD)
