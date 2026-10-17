import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from classify_extract import parse_llm_json


def test_parses_plain_json():
    r = parse_llm_json('{"is_listing": true, "is_single": true, "zone": "상계5구역"}')
    assert r["is_listing"] is True and r["zone"] == "상계5구역"


def test_strips_code_fence():
    r = parse_llm_json('```json\n{"is_listing": false, "is_single": false}\n```')
    assert r["is_listing"] is False


def test_returns_none_on_garbage():
    assert parse_llm_json("죄송하지만 JSON을 만들 수 없습니다") is None


def test_returns_none_on_none_input():
    assert parse_llm_json(None) is None
