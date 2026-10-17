import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from crawler import parse_list_page, normalize_date


def test_normalize_date():
    assert normalize_date("2026. 6. 6.") == "2026-06-06"
    assert normalize_date("2026. 12. 25.") == "2026-12-25"


def test_parse_list_page_extracts_logno_title():
    sample = '{"logNo":"223001","title":"%EC%83%81%EA%B3%84","addDate":"2026. 6. 1."}' \
             '{"logNo":"223002","title":"test","addDate":"2026. 6. 2."}'
    posts = parse_list_page(sample)
    assert len(posts) == 2
    assert posts[0]["log_no"] == "223001"
    assert posts[1]["log_no"] == "223002"
    assert posts[1]["title"] == "test"
    assert posts[0]["title"] == "상계"
