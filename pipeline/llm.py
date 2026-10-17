#!/usr/bin/env python3
"""claude CLI(OAuth) 1회 호출 래퍼 — API 0원. song_han/claude_oauth.py 패턴."""
import os, shutil, subprocess
from pathlib import Path
from typing import Optional


def _find_claude() -> Optional[str]:
    found = shutil.which("claude")
    if found:
        return found
    for cand in ["~/.local/bin/claude", "/opt/homebrew/bin/claude", "/usr/local/bin/claude"]:
        p = Path(cand).expanduser()
        if p.exists():
            return str(p)
    return None


CLAUDE_BIN = _find_claude()


def ask_claude(prompt: str, model: str = "sonnet", timeout: int = 120) -> Optional[str]:
    """프롬프트 1회 호출, stdout 반환. 실패/타임아웃 시 None."""
    if not CLAUDE_BIN:
        print("❌ claude CLI 없음")
        return None
    env = dict(os.environ)
    env.setdefault("HOME", os.path.expanduser("~"))
    env["PATH"] = os.pathsep.join(
        [os.path.dirname(CLAUDE_BIN), os.path.expanduser("~/.local/bin"), env.get("PATH", "")]
    )
    try:
        r = subprocess.run([CLAUDE_BIN, "-p", "--model", model, prompt],
                           capture_output=True, text=True, timeout=timeout, env=env)
    except Exception as e:
        print(f"❌ claude -p 실패: {e}")
        return None
    if r.returncode != 0:
        print(f"❌ claude -p 종료코드 {r.returncode}: {(r.stderr or '')[:200]}")
        return None
    return (r.stdout or "").strip() or None


if __name__ == "__main__":
    print("claude:", CLAUDE_BIN)
    print("응답:", ask_claude("Reply with exactly: LLM_OK", timeout=60))
