import datagokr


SAMPLE = {
    "HOUSE_MANAGE_NO": "2026910185",
    "HOUSE_NM": "포레나더샵 인천시청역(2차)",
    "RCRIT_PBLANC_DE": "2026-07-16",
    "SUBSCRPT_RCEPT_BGNDE": "2026-07-21",
    "SUBSCRPT_RCEPT_ENDDE": "2026-07-21",
    "TOT_SUPLY_HSHLDCO": "10",
    "PBLANC_URL": "https://www.applyhome.co.kr/example",
}


def test_schedule_extracts_dates():
    s = datagokr.schedule(SAMPLE)
    assert s["rcept_bgn"] == "2026-07-21"
    assert s["rcept_end"] == "2026-07-21"
    assert s["pblanc_de"] == "2026-07-16"
    assert s["supply"] == 10
    assert s["url"] == "https://www.applyhome.co.kr/example"


def test_schedule_handles_missing_fields():
    s = datagokr.schedule({"HOUSE_MANAGE_NO": "1"})
    assert s["rcept_bgn"] is None
    assert s["rcept_end"] is None
    assert s["supply"] is None


def test_schedule_handles_non_numeric_supply():
    s = datagokr.schedule({"TOT_SUPLY_HSHLDCO": ""})
    assert s["supply"] is None


def test_days_left_counts_from_given_today():
    import datetime
    d = datagokr.days_left("2026-07-25", today=datetime.date(2026, 7, 20))
    assert d == 5


def test_days_left_returns_none_without_date():
    assert datagokr.days_left(None) is None


def test_days_left_negative_when_past():
    import datetime
    d = datagokr.days_left("2026-07-18", today=datetime.date(2026, 7, 20))
    assert d == -2
