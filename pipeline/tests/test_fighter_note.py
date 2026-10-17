import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from generate import build_note_prompt


def test_prompt_includes_intro_text():
    p = build_note_prompt("상계5구역", "조합설립인가", "이 매물 무조건 오릅니다 마지막 기회!")
    assert "이 매물 무조건 오릅니다 마지막 기회!" in p


def test_prompt_has_guardrails():
    p = build_note_prompt("상계5구역", "조합설립인가", "소개글")
    assert "확정" in p
    assert "중립" in p or "단정" in p
    assert "한 줄" in p or "한줄" in p


def test_prompt_forbids_invented_numbers():
    p = build_note_prompt("상계5구역", "조합설립인가", "소개글")
    assert "지어내지" in p or "창작" in p
