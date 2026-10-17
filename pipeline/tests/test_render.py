import sys, asyncio, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from render import render_card

DATA = {
    "zone": "상계뉴타운 5구역", "stage": "조합설립인가", "location": "노원구 상계동",
    "transit": "4호선 도보권", "price": "4.2억", "premium": "1.1억",
    "rights_value": "3.1억", "expected_movein": "2032~", "area": "59㎡",
    "fighter_note": "5천만원대로 노려볼 라인", "source_name": "○○부동산 블로그",
}


def test_single_layout_makes_one_png():
    out = Path(tempfile.mkdtemp())
    d = dict(DATA); d["transit"] = None; d["rights_value"] = None
    d["expected_movein"] = None; d["area"] = None
    paths = asyncio.run(render_card(d, out, "L1"))
    assert len(paths) == 1
    assert paths[0].exists() and paths[0].stat().st_size > 1000


def test_carousel_layout_makes_four_png():
    out = Path(tempfile.mkdtemp())
    paths = asyncio.run(render_card(DATA, out, "L2"))
    assert len(paths) == 4
    for p in paths:
        assert p.exists() and p.stat().st_size > 1000


def test_png_is_1080_square():
    from PIL import Image
    out = Path(tempfile.mkdtemp())
    d = dict(DATA); d["transit"] = None; d["rights_value"] = None
    d["expected_movein"] = None; d["area"] = None
    paths = asyncio.run(render_card(d, out, "L3"))
    w, h = Image.open(paths[0]).size
    assert (w, h) == (1080, 1080)
