import margin as M


def test_저가단지_푼돈마진은_강추가_아니다():
    """5억 단지가 15% 싸도 마진은 0.75억. 구버전은 '무조건 신청!'이었다."""
    r = M.decide(bunyang=4.25, sise=5.0)
    assert r["decision"] == "고민해볼만해요"
    assert r["tier"] == 2
    assert round(r["margin"], 2) == 0.75


def test_고가단지_큰마진은_강추다():
    """30억 단지가 5%만 싸도 마진 1.5억이면 강추."""
    r = M.decide(bunyang=28.5, sise=30.0)
    assert r["decision"] == "무조건 신청!"
    assert r["tier"] == 3


def test_비율가드가_고가단지_오차를_강등시킨다():
    """마진 1.5억이어도 비율 3% 미만이면 시세 오차일 수 있어 한 단계 강등."""
    r = M.decide(bunyang=58.5, sise=60.0)
    assert round(r["margin"], 2) == 1.5
    assert r["cheap_pct"] < 3
    assert r["tier"] == 2
    assert r["decision"] == "고민해볼만해요"


def test_비율가드_경계_3퍼센트는_통과():
    r = M.decide(bunyang=48.5, sise=50.0)
    assert round(r["cheap_pct"], 2) == 3.0
    assert r["tier"] == 3


def test_실제_평택고덕_건은_애매한_가격대():
    """구버전에서 '고민해볼만해요'로 발행됐던 실제 건. 마진 0.37억."""
    r = M.decide(bunyang=5.53, sise=5.90)
    assert r["decision"] == "애매한 가격대"
    assert r["tier"] == 1


def test_실제_인천_건은_촉수엄금():
    """마진 -1.08억(시세보다 비쌈)."""
    r = M.decide(bunyang=6.46, sise=5.38)
    assert r["decision"] == "촉수엄금!"
    assert r["tier"] == 0
    assert r["margin"] < 0


def test_비쌀때_문구가_비쌈을_말한다():
    r = M.decide(bunyang=6.46, sise=5.38)
    assert "비쌉니다" in r["mean"]
    assert "옆 신축" in r["tail"]


def test_쌀때_문구가_쌈을_말한다():
    r = M.decide(bunyang=28.5, sise=30.0)
    assert "쌉니다" in r["mean"]


def test_시세가_0이면_안전하게_처리():
    r = M.decide(bunyang=5.0, sise=0)
    assert r["cheap_pct"] == 0
    assert r["tier"] == 0


def test_피드게이트는_tier3과_신뢰도를_함께_본다():
    assert M.feed_eligible(tier=3, confidence="ok") is True
    assert M.feed_eligible(tier=3, confidence="low") is True
    assert M.feed_eligible(tier=3, confidence="very_low") is False
    assert M.feed_eligible(tier=2, confidence="ok") is False


def test_부동소수점_오차로_컷을_놓치지_않는다():
    """마진이 수학적으로 정확히 1.50억인 입력. 반올림 없이 비교하면 1.4999...로 탈락한다."""
    r = M.decide(bunyang=3.02, sise=4.52)
    assert r["margin"] == 1.5
    assert r["tier"] == 3


def test_부동소수점_오차로_비율가드가_오탐하지_않는다():
    """cheap이 수학적으로 정확히 3.00%인 입력. 반올림 없이 비교하면 2.9999...로 강등된다."""
    r = M.decide(bunyang=52.38, sise=54.0)
    assert r["cheap_pct"] == 3.0
    assert r["tier"] == 3


def test_광역폴백은_표본이_넉넉할때만_통과():
    wide = "시군구 신축 유사평형 중위(3건·광역참고)"
    assert M.feed_eligible(3, "low", wide) is False
    assert M.feed_eligible(3, "ok", wide) is True


def test_동일단지_폴백은_low여도_통과():
    same = "동일단지 실거래 중위(3건)"
    assert M.feed_eligible(3, "low", same) is True


def test_basis_없으면_기존_동작_유지():
    assert M.feed_eligible(3, "low") is True
    assert M.feed_eligible(3, "very_low") is False
