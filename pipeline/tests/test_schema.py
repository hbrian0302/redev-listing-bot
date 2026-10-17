import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from schema import decide_layout, OPTIONAL_FIELDS


def test_optional_fields_are_the_four():
    assert OPTIONAL_FIELDS == ("transit", "rights_value", "expected_movein", "area")


def test_single_when_zero_optional():
    data = {"transit": None, "rights_value": None, "expected_movein": None, "area": None}
    assert decide_layout(data) == "single"


def test_single_when_one_optional():
    data = {"transit": "4호선 도보권", "rights_value": None, "expected_movein": None, "area": None}
    assert decide_layout(data) == "single"


def test_carousel_when_two_optional():
    data = {"transit": "4호선", "rights_value": "3.1억", "expected_movein": None, "area": None}
    assert decide_layout(data) == "carousel"


def test_carousel_when_all_optional():
    data = {"transit": "4호선", "rights_value": "3.1억", "expected_movein": "2032~", "area": "59㎡"}
    assert decide_layout(data) == "carousel"


def test_empty_string_counts_as_missing():
    # transit/rights_value are empty/whitespace (must NOT count); only area is genuinely filled.
    # 1 valid optional field → single. Proves empty/whitespace don't reach the threshold of 2.
    data = {"transit": "", "rights_value": "  ", "expected_movein": None, "area": "59㎡"}
    assert decide_layout(data) == "single"
