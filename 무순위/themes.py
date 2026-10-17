"""카드 다크 테마 5종. 피드 단조로움 방지용으로 공고별 로테이션.
공통: 흰 텍스트 + 회색 보조. 결정 배지는 의미색 고정(나쁨=coral / 좋음=mint / 중립=accent)."""

THEMES = [
    {"key": "indigo", "bg": "#0b0b0d", "surf": "#17171b", "track": "#26262c", "accent": "#8e9bf5"},
    {"key": "cyan",   "bg": "#0a1418", "surf": "#10222a", "track": "#1d3540", "accent": "#4fd1e0"},
    {"key": "amber",  "bg": "#14110a", "surf": "#231d10", "track": "#3a3018", "accent": "#f0b429"},
    {"key": "mint",   "bg": "#0a1410", "surf": "#10231a", "track": "#1c3a2c", "accent": "#4ade80"},
    {"key": "rose",   "bg": "#140a10", "surf": "#26121d", "track": "#3a1c2c", "accent": "#f472b6"},
]
WHITE = "#ffffff"
GRAY = "#9a9aa2"
BAD = "#ff6b6b"    # 촉수엄금·애매 등 부정
GOOD = "#4ade80"   # 무조건 신청·고민해볼만 등 긍정


def theme_for(seq: int) -> dict:
    """공고 순번(또는 날짜정수)으로 테마 로테이션."""
    return THEMES[seq % len(THEMES)]


def decision_color(decision: str, accent: str) -> str:
    if decision in ("촉수엄금!", "애매한 가격대"):
        return BAD
    if decision in ("무조건 신청!", "고민해볼만해요"):
        return GOOD
    return accent
