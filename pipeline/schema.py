"""매물 카드 데이터 스키마 + 표현 로직 (순수 함수)."""

# 캡션 CTA에 넣을 대표 텔레그램 핸들(리드 DM 창구). 브랜드명은 "재미나이".
TELEGRAM_HANDLE = "@your_handle"

REQUIRED_FIELDS = ("zone", "stage", "location", "price", "premium", "fighter_note", "source_name")
OPTIONAL_FIELDS = ("transit", "rights_value", "expected_movein", "area")
ALL_DATA_FIELDS = REQUIRED_FIELDS + OPTIONAL_FIELDS + ("source_url",)

# 단일 1장에 노출하는 핵심 필드(나머지는 캐러셀 정보장에서만)
SINGLE_FIELDS = ("zone", "stage", "location", "price", "premium", "fighter_note", "source_name")


def _filled(v) -> bool:
    return v is not None and str(v).strip() != ""


def decide_layout(data: dict) -> str:
    """선택 필드(4개) 중 2개 이상 유효하면 'carousel', 아니면 'single'."""
    n = sum(1 for f in OPTIONAL_FIELDS if _filled(data.get(f)))
    return "carousel" if n >= 2 else "single"


def build_caption(data: dict, handle: str = TELEGRAM_HANDLE) -> str:
    """발행용 캡션(이모지 없음). 역할 분리 — 거래 문의는 현장 중개사, 진단·상담은 대표 텔레그램."""
    zone = data.get("zone", "").strip()
    stage = data.get("stage", "").strip()
    note = (data.get("fighter_note") or "").strip()
    src = data.get("source_name", "").strip()
    phone = (data.get("source_phone") or "").strip()
    head = f"{zone} · {stage}".rstrip(" ·")
    lines = [head]
    if note:
        lines.append(note)
    broker = f"매물 문의 · {src}" + (f" {phone}" if phone else "")
    lines.append(broker)
    lines.append(f"내 구역 무료진단·재테크 상담 → 텔레그램 {handle}")
    return "\n".join(lines)
