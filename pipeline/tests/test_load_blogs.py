import sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from discover import parse_broker_csv


def _write(tmp, text):
    p = Path(tmp) / "중개사_소스.csv"
    p.write_text(text, encoding="utf-8-sig")
    return p


HEADER = "블로그ID,블로그URL,중개사명,전화번호,전화_유효,담당구역코드,담당구역수,상태\n"


def test_only_active_rows():
    tmp = tempfile.mkdtemp()
    p = _write(tmp, HEADER +
               "broker_a,https://blog.naver.com/broker_a,가나다 부동산,,N,hannam-3,1,active\n"
               "noisy1,https://blog.naver.com/noisy1,잡블로그,,N,,0,노이즈의심\n"
               "broker_b,https://blog.naver.com/broker_b,중개사B,02-1,Y,hannam-3,1,active\n")
    blogs = parse_broker_csv(p)
    assert len(blogs) == 2
    # 전화_유효=N → phone 빈값, Y → 전화번호 담김
    assert blogs[0] == {"blog_id": "broker_a", "name": "가나다 부동산", "phone": ""}
    assert blogs[1] == {"blog_id": "broker_b", "name": "중개사B", "phone": "02-1"}


def test_blank_name_falls_back_to_id():
    tmp = tempfile.mkdtemp()
    p = _write(tmp, HEADER + "abc123,https://blog.naver.com/abc123,,,N,x,1,active\n")
    blogs = parse_broker_csv(p)
    assert blogs[0] == {"blog_id": "abc123", "name": "abc123", "phone": ""}


def test_phone_only_when_valid():
    # 전화번호가 있어도 전화_유효=N이면 phone 빈값(허위·불명 번호 노출 방지)
    tmp = tempfile.mkdtemp()
    p = _write(tmp, HEADER + "xx,https://blog.naver.com/xx,중개Y,010-1,N,x,1,active\n")
    assert parse_broker_csv(p)[0]["phone"] == ""


def test_bom_header_handled():
    # utf-8-sig로 써서 BOM이 첫 컬럼명을 오염시키지 않는지(블로그ID 인식) 확인
    tmp = tempfile.mkdtemp()
    p = _write(tmp, HEADER + "zz,https://blog.naver.com/zz,중개사Z,02-9,Y,x,1,active\n")
    blogs = parse_broker_csv(p)
    assert blogs == [{"blog_id": "zz", "name": "중개사Z", "phone": "02-9"}]
