"""지오코딩(네이버 클라우드) + 정적지도 + OpenStreetMap Overpass POI(역·초등·공원)."""
from __future__ import annotations
import math, base64
import requests, httpx

GEO = "https://maps.apigw.ntruss.com/map-geocode/v2/geocode"
STATIC = "https://maps.apigw.ntruss.com/map-static/v2/raster"
OVERPASS = "https://overpass-api.de/api/interpreter"

def _keys():
    import keyring
    return (keyring.get_password("redev_market", "naver_map_id"),
            keyring.get_password("redev_market", "naver_map_secret"))

def _hdr(kid, ksec):
    return {"X-NCP-APIGW-API-KEY-ID": kid, "X-NCP-APIGW-API-KEY": ksec}


import re

def _clean_variants(address: str):
    """신도시 블록주소 등 지오코딩 실패 대비 — 점점 짧게."""
    a = (address or "").strip()
    yield a
    b = re.sub(r"\s*(내|일원)\b.*$", "", a)                 # '내 Abc-36블록' / '일원' 제거
    b = re.sub(r"\s*[A-Za-z0-9\-]+블록.*$", "", b).strip()
    if b and b != a:
        yield b
    m = re.match(r"(\S+(?:시|군))\s+(\S+(?:구|동|읍|면))", a)  # 시군구 + 동/읍
    if m:
        yield f"{m.group(1)} {m.group(2)}"
    m2 = re.match(r"(\S+(?:특별시|광역시|도|시))\s+(\S+(?:시|군|구))", a)
    if m2:
        yield f"{m2.group(1)} {m2.group(2)}"


def _geo_raw(address: str):
    kid, ksec = _keys()
    for q in _clean_variants(address):
        r = requests.get(GEO, params={"query": q}, headers=_hdr(kid, ksec), timeout=12)
        if r.status_code == 200:
            a = r.json().get("addresses", [])
            if a:
                return a[0]
    return None


def geocode(address: str) -> tuple[float, float] | None:
    """주소 → (lng, lat). 신도시 블록주소면 점점 짧게 재시도."""
    a = _geo_raw(address)
    return (float(a["x"]), float(a["y"])) if a else None


def geocode_dong(address: str) -> tuple[tuple[float, float] | None, str | None]:
    """→ ((lng,lat), 법정동명). 시세 비교를 동 단위로 좁히는 용도."""
    a = _geo_raw(address)
    if not a:
        return None, None
    dong = None
    for e in a.get("addressElements", []):
        if "DONGMYUN" in (e.get("types") or []):
            dong = e.get("longName") or None
    return (float(a["x"]), float(a["y"])), dong


def static_map_datauri(lng: float, lat: float, w=1000, h=560, level=16) -> str | None:
    kid, ksec = _keys()
    params = {"w": w, "h": h, "center": f"{lng},{lat}", "level": level, "scale": 2,
              "markers": f"type:d|size:mid|pos:{lng} {lat}"}
    r = requests.get(STATIC, params=params, headers=_hdr(kid, ksec), timeout=15)
    if r.status_code != 200:
        return None
    return "data:image/jpeg;base64," + base64.b64encode(r.content).decode()


def _dist_m(lng, lat, lng2, lat2):
    return math.hypot((lng2 - lng) * 88500, (lat2 - lat) * 111000)

def walk_min(m):
    return max(1, round(m / 67))


def nearest_poi(lng: float, lat: float) -> dict:
    """반경 내 최근접 지하철역·초등학교·공원 → {'역':(name,walk), '초등':..., '공원':...} (없으면 None)."""
    q = (f'[out:json][timeout:25];('
         f'node(around:1800,{lat},{lng})["railway"~"station"];'
         f'node(around:1800,{lat},{lng})["amenity"="school"];way(around:1800,{lat},{lng})["amenity"="school"];'
         f'node(around:1400,{lat},{lng})["leisure"="park"];way(around:1400,{lat},{lng})["leisure"="park"];'
         f');out center tags;')
    try:
        els = httpx.post(OVERPASS, data={"data": q}, timeout=60, headers={"User-Agent": "redev-listing-bot/1.0"}).json()["elements"]
    except Exception:
        return {"역": None, "초등": None, "공원": None}

    def near(pred):
        best = None
        for e in els:
            t = e.get("tags", {})
            if not pred(t):
                continue
            la = e.get("lat") or e.get("center", {}).get("lat")
            lo = e.get("lon") or e.get("center", {}).get("lon")
            if la is None:
                continue
            d = _dist_m(lng, lat, lo, la)
            if best is None or d < best[1]:
                best = (t.get("name", "역"), d)
        return (best[0], walk_min(best[1])) if best else None

    return {
        "역": near(lambda t: t.get("railway") in ("station", "halt") or t.get("station") == "subway"),
        "초등": near(lambda t: t.get("amenity") == "school" and "초등" in t.get("name", "")),
        "공원": near(lambda t: t.get("leisure") == "park"),
    }
