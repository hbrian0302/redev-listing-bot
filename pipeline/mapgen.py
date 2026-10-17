"""네이버 클라우드 Static Map — 구역 위치 → 핀 찍힌 지도 이미지(data URI).
키는 keyring(redev_market/naver_map_id, naver_map_secret)에서만 읽는다(코드·git에 평문 없음).
신버전 도메인 maps.apigw.ntruss.com 사용. 실패 시 None → 슬라이드3 placeholder로 폴백.
"""
import base64
from typing import Optional
import requests

GEO = "https://maps.apigw.ntruss.com/map-geocode/v2/geocode"
STATIC = "https://maps.apigw.ntruss.com/map-static/v2/raster"


def _keys():
    try:
        import keyring
        return (keyring.get_password("redev_market", "naver_map_id"),
                keyring.get_password("redev_market", "naver_map_secret"))
    except Exception:
        return None, None


def _headers(kid: str, ksec: str) -> dict:
    return {"X-NCP-APIGW-API-KEY-ID": kid, "X-NCP-APIGW-API-KEY": ksec}


def geocode(query: str, kid: str, ksec: str):
    """주소/지명 → (lng, lat). 없으면 None."""
    r = requests.get(GEO, params={"query": query}, headers=_headers(kid, ksec), timeout=12)
    r.raise_for_status()
    addrs = r.json().get("addresses", [])
    if not addrs:
        return None
    return float(addrs[0]["x"]), float(addrs[0]["y"])


def static_map_datauri(location: str, w: int = 760, h: int = 320, level: int = 15) -> Optional[str]:
    """location(예:'노원구 상계동') → 핀 찍힌 지도 data URI. 키 없거나 실패 시 None."""
    kid, ksec = _keys()
    if not (kid and ksec) or not (location or "").strip():
        return None
    q = location.strip()
    if not q.startswith("서울"):
        q = "서울 " + q
    try:
        coord = geocode(q, kid, ksec)
        if not coord:
            return None
        lng, lat = coord
        params = {
            "w": w, "h": h, "center": f"{lng},{lat}", "level": level, "scale": 2,
            "markers": f"type:d|size:mid|pos:{lng} {lat}",
        }
        r = requests.get(STATIC, params=params, headers=_headers(kid, ksec), timeout=15)
        if r.status_code != 200:
            return None
        mime = r.headers.get("content-type", "image/jpeg").split(";")[0]
        return f"data:{mime};base64," + base64.b64encode(r.content).decode()
    except Exception:
        return None


if __name__ == "__main__":
    import sys
    loc = sys.argv[1] if len(sys.argv) > 1 else "노원구 상계동"
    uri = static_map_datauri(loc)
    print(f"{loc} → {'지도 OK, ' + str(len(uri)) + '자' if uri else '실패(None)'}")
