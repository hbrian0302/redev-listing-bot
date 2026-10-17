import review_bot as RB


def test_신형_레코드는_스레드캡션을_보여준다():
    d = {"caption_threads": "스레드용", "caption_ig": "인스타용"}
    assert RB.preview_caption(d) == "스레드용"


def test_구형_레코드는_caption을_보여준다():
    d = {"caption": "구버전"}
    assert RB.preview_caption(d) == "구버전"


def test_아무것도_없으면_빈문자열():
    assert RB.preview_caption({}) == ""


def test_편집시_두_필드를_함께_갱신():
    d = {"caption_threads": "옛날", "caption_ig": "옛날인스타"}
    out = RB.apply_edit(d, "새 캡션")
    assert out["caption_threads"] == "새 캡션"
    assert out["caption_ig"] == "새 캡션"
    assert out["edited"] is True


def test_편집은_원본을_변형하지_않는다():
    d = {"caption_threads": "옛날"}
    RB.apply_edit(d, "새것")
    assert d["caption_threads"] == "옛날"
