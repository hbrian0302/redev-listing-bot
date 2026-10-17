#!/usr/bin/env python3
"""무순위 캡션 생성 — fact 화이트리스트 기반 LLM 생성 + 무날조 검증.

캡션은 채널별로 2종이다.
  - 스레드용: 6~7행, 약 200자. 훅 + 비교시세 + 마감 + CTA
  - 인스타용: 12~15행. 위 + 배경해석 + 대상 + 면책

숫자·날짜는 반드시 build_facts()가 넘긴 값만 쓴다. violations()가 이를 강제한다.
"""
from __future__ import annotations
import re

# "6.46억", "6억 4600만원", "5000만원"을 모두 잡는다.
# 만원 단독은 "원"을 요구해서 "30만 명"이 오탐되지 않게 한다.
_MONEY_RE = re.compile(
    r"(?P<eok>\d+(?:\.\d+)?)\s*억(?:\s*(?P<man>\d+)\s*만\s*원?)?"
    r"|(?P<man_only>\d+)\s*만\s*원"
)
_DATE_RE = re.compile(r"(\d{1,2})월\s*(\d{1,2})일")
# "D-3", "5일 남았어", "3일 뒤" 를 잡는다.
# "7월 21일 하루야" 처럼 날짜 뒤에 오는 "일"은 남/뒤 접미사가 없어 매치되지 않는다.
_DLEFT_RE = re.compile(r"D-\s*(\d+)|(\d+)\s*일\s*(?:남|뒤)")


def build_facts(data: dict, dec: dict, sch: dict, days_left: int | None) -> dict:
    """파이프라인 값 → LLM에 넘길 사실 딕셔너리. 여기 없는 숫자는 캡션에 못 쓴다."""
    name = f'{data.get("name_l1", "")} {data.get("name_l2", "")}'.strip()
    sub = data.get("sub") or ""
    return {
        "name": name,
        "region": sub.split(" · ")[0] if " · " in sub else sub,
        "bunyang": data.get("bunyang"),
        "sise": data.get("sise"),
        "margin": round(dec.get("margin", 0), 2),
        "rcept_bgn": sch.get("rcept_bgn"),
        "rcept_end": sch.get("rcept_end"),
        "days_left": days_left,
        "movein": sub.split("입주 ")[-1] if "입주 " in sub else None,
        "decision": data.get("decision"),
        "basis": data.get("basis"),
    }


def _allowed_amounts(facts: dict) -> set[float]:
    """캡션에 등장해도 되는 금액(억). 소수점 절사·반올림 표기도 허용."""
    out: set[float] = set()
    for k in ("bunyang", "sise", "margin"):
        v = facts.get(k)
        if v is None:
            continue
        v = abs(round(float(v), 2))
        out.add(v)
        out.add(float(int(v)))       # 6.46 → 6 ("6억대" 허용)
        out.add(round(v, 1))         # 6.46 → 6.5 반올림 표기 허용
    return out


def _allowed_dates(facts: dict) -> set[tuple[int, int]]:
    out: set[tuple[int, int]] = set()
    for k in ("rcept_bgn", "rcept_end"):
        v = facts.get(k)
        if not v:
            continue
        try:
            _y, m, d = v.split("-")
            out.add((int(m), int(d)))
        except ValueError:
            continue
    return out


def _money_hits(text: str):
    """(억 단위 값, 원문 표기) 목록. 억·만원·복합 표기를 모두 환산한다."""
    out = []
    for m in _MONEY_RE.finditer(text):
        if m.group("eok") is not None:
            v = float(m.group("eok"))
            if m.group("man"):
                v += int(m.group("man")) / 10000
        else:
            v = int(m.group("man_only")) / 10000
        out.append((round(v, 4), m.group(0).strip()))
    return out


def violations(text: str, facts: dict) -> list[str]:
    """캡션에서 fact에 없는 금액·날짜·남은 일수를 찾아 목록으로 반환. 빈 리스트면 통과."""
    bad: list[str] = []
    ok_amt = _allowed_amounts(facts)
    for v, raw in _money_hits(text):
        if not any(abs(v - a) < 0.005 for a in ok_amt):
            bad.append(raw)
    ok_date = _allowed_dates(facts)
    for mm, dd in _DATE_RE.findall(text):
        if (int(mm), int(dd)) not in ok_date:
            bad.append(f"{int(mm)}월 {int(dd)}일")
    days_left = facts.get("days_left")
    if days_left is not None:
        for m in _DLEFT_RE.finditer(text):
            n = int(m.group(1) or m.group(2))
            if n != int(days_left):
                bad.append(f"D-{n}")
    return bad


_TONE = """너는 재개발·청약 정보를 올리는 인스타/스레드 계정 운영자다.
독자를 "여러분"이라 부르고, 친근한 구어체로 쓴다.

톤 규칙:
- "~같아", "~하더라고", "~볼 만하고" 처럼 낮춰서 공유하듯 쓴다
- 단정·명령형 금지: "무조건", "~해라", "이건 함정이다" 같은 표현 쓰지 마라
- 판단을 내려주지 말고 근거를 놓고 "나는 이렇게 본다" 정도로 물러난다

금지 사항:
- "분양가 X vs 시세 Y" 같은 라벨:값 나열 금지 (카드 이미지에 이미 있다)
- 내부 약어 노출 금지: "브역대신평공초", "입지 60점 B등급" 같은 표현 쓰지 마라
- 텔레그램 계정·외부 링크 언급 금지
- 이모지는 마지막 CTA에 🙏 하나만

⚠️ 가장 중요: 아래 '사실' 목록에 없는 숫자·금액·날짜를 절대 지어내지 마라.
현금 보유액, 계약금, 경쟁률, 세대수처럼 목록에 없는 수치는 언급 자체를 하지 마라.
숫자 없이 표현할 수 있으면 그렇게 써라."""

_CH = {
    "threads": """형식: 6~7행, 약 200자. 짧게.
1행: "여러분~"로 시작하는 훅 한 줄
2~4행: 비교 시세 하나만 놓고 왜 이 가격인지
5행: 접수일과 D-N
6행: 좋아요·팔로우 요청 (텔레그램 언급 금지)
면책 문구는 넣지 마라.""",
    "instagram": """형식: 12~15행.
1행: "여러분~"로 시작하는 훅 한 줄
2~5행: 비교 시세 + 왜 이 가격이 나왔는지 배경 해석
6~8행: 누가 넣어볼 만한지 (단, 금액이 필요한 조건은 숫자 없이 서술)
9행: 접수일과 D-N
10~11행: 좋아요·팔로우 요청 + 팔로우해두면 놓치지 않는다는 이유
마지막행: "분양가는 공고 기준(옵션 별도), 시세는 최근 실거래야." """,
}


def _prompt(facts: dict, channel: str, retry_note: str = "") -> str:
    lines = [f"- {k}: {v}" for k, v in facts.items() if v is not None]
    return (f"{_TONE}\n\n{_CH[channel]}\n\n"
            f"사실 목록 (여기 있는 값만 써라):\n" + "\n".join(lines) +
            (f"\n\n{retry_note}" if retry_note else "") +
            "\n\n캡션 본문만 출력해라. 설명이나 따옴표 없이.")


def _claude(prompt: str) -> str:
    """claude -p (OAuth) 호출. API 비용 없음. keychain을 쓰므로 launchd 실행 필수."""
    import subprocess
    r = subprocess.run(["claude", "-p", prompt], capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        raise RuntimeError(f"claude -p 실패: {r.stderr[:200]}")
    return r.stdout.strip()


def _fallback(facts: dict, channel: str) -> str:
    """LLM이 계속 날조할 때 쓰는 안전 템플릿. 사실만 최소한으로 담는다."""
    when = ""
    if facts.get("rcept_bgn"):
        try:
            _y, m, d = facts["rcept_bgn"].split("-")
            when = f"접수는 {int(m)}월 {int(d)}일이야."
        except ValueError:
            when = ""
    dl = facts.get("days_left")
    if when and dl is not None and dl >= 0:
        when += f" D-{dl}"
    head = f"여러분~ {facts.get('region', '')} {facts.get('name', '')} 무순위 나왔어.".replace("  ", " ")
    body = "가격이랑 인근 시세는 카드에 정리해뒀어. 한번 보고 판단해봐."
    cta = "도움 됐으면 좋아요~ 줍줍 계속 올릴 테니 팔로우도 부탁해🙏"
    parts = [head, "", body, "", when, "", cta]
    if channel == "instagram":
        parts += ["", "분양가는 공고 기준(옵션 별도), 시세는 최근 실거래야."]
    return "\n".join(p for p in parts if p is not None).strip()


def generate(facts: dict, channel: str, llm=None, max_retry: int = 2) -> str:
    """채널별 캡션 생성. 무날조 검증을 통과할 때까지 재시도, 실패 시 안전 템플릿."""
    if channel not in _CH:
        raise ValueError(f"알 수 없는 채널: {channel}")
    llm = llm or _claude
    note = ""
    for _ in range(max_retry):
        try:
            text = llm(_prompt(facts, channel, note))
        except Exception:
            break
        bad = violations(text, facts)
        if not bad:
            return text
        note = ("직전 시도에서 사실 목록에 없는 값을 썼다: "
                + ", ".join(bad) + ". 이 값들을 빼고 다시 써라.")
    return _fallback(facts, channel)
