import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from schema import build_caption

DATA = {
    "zone": "상계뉴타운 5구역", "stage": "조합설립인가", "location": "노원구 상계동",
    "price": "4.2억", "premium": "1.1억", "fighter_note": "5천만원대로 노려볼 라인",
    "source_name": "○○부동산 블로그",
}


def test_caption_includes_zone_and_hook():
    cap = build_caption(DATA)
    assert "상계뉴타운 5구역" in cap
    assert "5천만원대로 노려볼 라인" in cap


def test_caption_has_broker_line_and_reserved_role():
    # 거래 문의는 중개사, 진단·상담은 대표(재테크 상담)
    cap = build_caption(DATA)
    assert "매물 문의" in cap and "○○부동산 블로그" in cap
    assert "재테크 상담" in cap


def test_caption_broker_phone_when_present():
    d = dict(DATA); d["source_phone"] = "02-935-1234"
    cap = build_caption(d)
    assert "02-935-1234" in cap


def test_caption_no_emoji():
    # 이모지 전부 제거
    cap = build_caption(DATA)
    for e in ("📍", "🏢", "💬", "☎"):
        assert e not in cap


def test_caption_has_telegram_cta():
    cap = build_caption(DATA, handle="@테스트핸들")
    assert "텔레그램" in cap
    assert "@테스트핸들" in cap


def test_caption_broker_present_even_if_fighter_note_empty():
    d = dict(DATA); d["fighter_note"] = ""
    cap = build_caption(d)
    assert "매물 문의" in cap and "텔레그램" in cap


def test_caption_default_handle_used_when_not_given():
    cap = build_caption(DATA)
    assert "텔레그램" in cap and "@" in cap  # 기본 핸들 자리 채워짐
