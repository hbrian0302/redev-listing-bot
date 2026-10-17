"""data.go.kr API 클라이언트 — 무순위 공고·주택형별·원분양·아파트 실거래.
serviceKey = keychain redev_market/datagokr_key (Encoding형 → unquote 후 사용)."""
from __future__ import annotations
import urllib.parse, xml.etree.ElementTree as ET
import httpx

_KEY = None
def key() -> str:
    global _KEY
    if _KEY is None:
        import keyring
        _KEY = urllib.parse.unquote(keyring.get_password("redev_market", "datagokr_key"))
    return _KEY

ODC = "https://api.odcloud.kr/api/ApplyhomeInfoDetailSvc/v1"
RTMS = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"
CAPITAL = {"서울", "경기", "인천"}


def _odc(op: str, per=500, **cond) -> list[dict]:
    p = {"serviceKey": key(), "page": "1", "perPage": str(per)}
    p.update(cond)
    r = httpx.get(f"{ODC}/{op}", params=p, timeout=60)
    return r.json().get("data", []) or []


def musunwi_list() -> list[dict]:
    """무순위/취소후재공급 공고 전체 → 수도권만."""
    rows = _odc("getRemndrLttotPblancDetail")
    return [r for r in rows if r.get("SUBSCRPT_AREA_CODE_NM") in CAPITAL]


def schedule(pub: dict) -> dict:
    """공고 dict → 일정·규모 정규화. 없는 값은 None."""
    def _int(v):
        try:
            return int(str(v).strip())
        except (TypeError, ValueError):
            return None
    g = lambda k: (pub.get(k) or None)
    return {
        "pblanc_de": g("RCRIT_PBLANC_DE"),
        "rcept_bgn": g("SUBSCRPT_RCEPT_BGNDE"),
        "rcept_end": g("SUBSCRPT_RCEPT_ENDDE"),
        "supply": _int(pub.get("TOT_SUPLY_HSHLDCO")),
        "url": g("PBLANC_URL"),
    }


def days_left(rcept_end: str | None, today=None) -> int | None:
    """접수 마감까지 남은 일수. 음수면 이미 마감. 날짜 없으면 None."""
    if not rcept_end:
        return None
    import datetime
    today = today or datetime.date.today()
    try:
        return (datetime.date.fromisoformat(rcept_end) - today).days
    except ValueError:
        return None


def musunwi_models(house_manage_no: str) -> list[dict]:
    """공고의 주택형별(전용·분양가 LTTOT_TOP_AMOUNT·세대)."""
    return _odc("getRemndrLttotPblancMdl", **{"cond[HOUSE_MANAGE_NO::EQ]": house_manage_no})


def original_total_supply(house_nm: str) -> int | None:
    """원분양(일반 APT분양) 공고에서 주택명 매칭 → 단지 총공급세대(대단지 판정용)."""
    core = house_nm.split("(")[0].strip()
    for r in _odc("getAPTLttotPblancDetail"):
        nm = r.get("HOUSE_NM") or ""
        if core and core[:6] in nm and (nm[:4] in core or core[:4] in nm):
            t = r.get("TOT_SUPLY_HSHLDCO")
            try:
                return int(t)
            except (TypeError, ValueError):
                return None
    return None


def apt_trades(lawd5: str, ymd: str) -> list[dict]:
    """아파트 매매 실거래(법정동코드5 + YYYYMM)."""
    r = httpx.get(RTMS, params={"serviceKey": key(), "LAWD_CD": lawd5, "DEAL_YMD": ymd, "numOfRows": "999"}, timeout=60)
    out = []
    try:
        for it in ET.fromstring(r.text).iter("item"):
            g = lambda t: (it.findtext(t) or "").strip()
            amt = g("dealAmount").replace(",", "")
            if not amt.isdigit():
                continue
            out.append({"apt": g("aptNm"), "ar": float(g("excluUseAr") or 0),
                        "amt": int(amt) / 10000, "year": g("buildYear"), "umd": g("umdNm")})
    except ET.ParseError:
        pass
    return out


# ── 수도권 시군구 법정동코드(LAWD_CD 5자리) ──
_LAWD = {
    # 서울 (충돌 구는 '서울 ' 접두)
    "서울 종로구": "11110", "서울 중구": "11140", "용산구": "11170", "성동구": "11200",
    "광진구": "11215", "동대문구": "11230", "중랑구": "11260", "성북구": "11290",
    "강북구": "11305", "도봉구": "11320", "노원구": "11350", "은평구": "11380",
    "서대문구": "11410", "마포구": "11440", "양천구": "11470", "서울 강서구": "11500",
    "구로구": "11530", "금천구": "11545", "영등포구": "11560", "동작구": "11590",
    "관악구": "11620", "서초구": "11650", "강남구": "11680", "송파구": "11710", "강동구": "11740",
    # 인천
    "인천 중구": "28110", "인천 동구": "28140", "미추홀구": "28177", "연수구": "28185",
    "남동구": "28200", "부평구": "28237", "계양구": "28245", "인천 서구": "28260",
    "강화군": "28710", "옹진군": "28720",
    # 경기 (구 있는 시: 시+구)
    "수원시 장안구": "41111", "수원시 권선구": "41113", "수원시 팔달구": "41115", "수원시 영통구": "41117",
    "성남시 수정구": "41131", "성남시 중원구": "41133", "성남시 분당구": "41135",
    "안양시 만안구": "41171", "안양시 동안구": "41173",
    "안산시 상록구": "41271", "안산시 단원구": "41273",
    "고양시 덕양구": "41281", "고양시 일산동구": "41285", "고양시 일산서구": "41287",
    "용인시 처인구": "41461", "용인시 기흥구": "41463", "용인시 수지구": "41465",
    "부천시 원미구": "41192", "부천시 소사구": "41194", "부천시 오정구": "41196", "부천시": "41190",
    # 경기 구 없는 시/군
    "의정부시": "41150", "광명시": "41210", "평택시": "41220", "동두천시": "41250",
    "과천시": "41290", "구리시": "41310", "남양주시": "41360", "오산시": "41370",
    "시흥시": "41390", "군포시": "41410", "의왕시": "41430", "하남시": "41450",
    "파주시": "41480", "이천시": "41500", "안성시": "41550", "김포시": "41570",
    "화성시": "41590", "광주시": "41610", "양주시": "41630", "포천시": "41650",
    "여주시": "41670", "연천군": "41800", "가평군": "41820", "양평군": "41830",
}
def resolve_lawd(address: str) -> str | None:
    """주소 문자열 → 시군구 LAWD_CD 5자리. 가장 구체적(긴) 매칭 우선."""
    a = (address or "").replace("특별시", "").replace("광역시", "").replace("경기도", "경기").replace("  ", " ")
    for name in sorted(_LAWD, key=len, reverse=True):
        if name in a:
            return _LAWD[name]
    return None
