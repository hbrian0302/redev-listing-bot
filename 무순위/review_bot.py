#!/usr/bin/env python3
"""무순위 카드 검수봇. queue/pending → 텔레그램(3장+캡션) → 승인/반려/캡션수정.
승인분은 queue/approved 로 이동(발행이 가져감)."""
from __future__ import annotations
import json, sys, time
from pathlib import Path
import httpx

BASE = Path(__file__).resolve().parent
Q = BASE / "queue"
PENDING, APPROVED, REJECTED = Q / "pending", Q / "approved", Q / "rejected"
for d in (PENDING, APPROVED, REJECTED):
    d.mkdir(parents=True, exist_ok=True)
STATE = Q / "_state.json"
FALLBACK_ENV = Path.home() / "agents/telegram-claude/.env"


def _keyring(k):
    try:
        import keyring; return keyring.get_password("redev_market", k)
    except Exception:
        return None

def _env(key):
    if FALLBACK_ENV.exists():
        for l in FALLBACK_ENV.read_text().splitlines():
            if l.strip().startswith(key + "="):
                return l.split("=", 1)[1].strip().strip('"').strip("'")
    return None

TOKEN = _keyring("review_bot_token")
CHAT = _keyring("review_chat_id") or _env("ALLOWED_USER_ID")
API = f"https://api.telegram.org/bot{TOKEN}"


def load_state():
    s = json.loads(STATE.read_text()) if STATE.exists() else {}
    s.setdefault("sent", {}); s.setdefault("offset", 0); s.setdefault("awaiting_edit", None)
    return s

def save_state(s): STATE.write_text(json.dumps(s, ensure_ascii=False, indent=2))

def api(method, **kw):
    try:
        return httpx.post(f"{API}/{method}", json=kw, timeout=60).json()
    except Exception as e:
        print("api err", method, e); return {"ok": False}

def keyboard(code):
    return {"inline_keyboard": [
        [{"text": "✅ 승인", "callback_data": f"ok:{code}"},
         {"text": "✏️ 캡션수정", "callback_data": f"ed:{code}"},
         {"text": "❌ 반려", "callback_data": f"no:{code}"}]]}


def preview_caption(d: dict) -> str:
    """검수 화면에 띄울 캡션. 신형은 스레드용, 구형은 caption 폴백."""
    return d.get("caption_threads") or d.get("caption") or ""


def apply_edit(d: dict, text: str) -> dict:
    """캡션 수동 편집 결과를 두 채널에 함께 반영한 새 dict을 반환."""
    out = dict(d)
    out["caption_threads"] = text
    out["caption_ig"] = text
    out["edited"] = True
    return out


def send_cards(images, caption, kb):
    media, files, fhs = [], {}, []
    try:
        for i, p in enumerate(images):
            fh = open(p, "rb"); fhs.append(fh)
            files[f"f{i}"] = (f"c{i}.png", fh, "image/png")
            item = {"type": "photo", "media": f"attach://f{i}"}
            if i == 0:
                item["caption"] = caption[:1024]
            media.append(item)
        httpx.post(f"{API}/sendMediaGroup", data={"chat_id": str(CHAT), "media": json.dumps(media)},
                   files=files, timeout=120)
    finally:
        for fh in fhs:
            fh.close()
    return api("sendMessage", chat_id=CHAT, text="↑ 무순위 카드 검수 (표본 작으면 반려)", reply_markup=kb)


def push_new(state):
    for f in sorted(PENDING.glob("*.json")):
        code = f.stem
        if code in state["sent"]:
            continue
        d = json.loads(f.read_text())
        res = send_cards(d["images"], preview_caption(d), keyboard(code))
        if res.get("ok"):
            state["sent"][code] = res["result"]["message_id"]; save_state(state)
            print(f"→ 검수 전송 {code}")


def move(code, dest, patch=None):
    src = PENDING / f"{code}.json"
    if not src.exists():
        return None
    d = json.loads(src.read_text())
    if patch:
        d.update(patch)
    (dest / f"{code}.json").write_text(json.dumps(d, ensure_ascii=False, indent=2))
    src.unlink(); return d


def handle_cb(cb, state):
    data = cb.get("data", ""); mid = cb["message"]["message_id"]; cid = cb["message"]["chat"]["id"]
    api("answerCallbackQuery", callback_query_id=cb["id"])
    if ":" not in data:
        return
    action, code = data.split(":", 1)
    if action == "ok":
        move(code, APPROVED)
        api("editMessageText", chat_id=cid, message_id=mid, text=f"✅ 승인됨 — 발행 대기 ({code})")
    elif action == "no":
        d = move(code, REJECTED)
        for img in (d or {}).get("images", []):
            try: Path(img).unlink()
            except Exception: pass
        api("editMessageText", chat_id=cid, message_id=mid, text=f"❌ 반려됨 ({code})")
    elif action == "ed":
        state["awaiting_edit"] = code; save_state(state)
        api("sendMessage", chat_id=cid, text=f"✏️ '{code}' 새 캡션을 답장으로 보내주세요(그대로 승인).")


def handle_msg(m, state):
    code = state.get("awaiting_edit"); text = (m.get("text") or "").strip()
    if not code or not text:
        return
    move(code, APPROVED, {"caption_threads": text, "caption_ig": text, "edited": True})
    state["awaiting_edit"] = None; save_state(state)
    api("sendMessage", chat_id=m["chat"]["id"], text=f"✏️→✅ '{code}' 수정 캡션으로 승인.")


def main():
    assert TOKEN, "봇 토큰 없음(keyring redev_market/review_bot_token)"
    assert CHAT, "chat id 없음"
    state = load_state()
    api("sendMessage", chat_id=CHAT, text="🟢 무순위 검수봇 시작.")
    print(f"● 무순위 검수봇 (chat={CHAT})")
    while True:
        push_new(state)
        for up in api("getUpdates", offset=state["offset"], timeout=30).get("result", []):
            state["offset"] = up["update_id"] + 1
            if "callback_query" in up:
                handle_cb(up["callback_query"], state)
            elif "message" in up:
                handle_msg(up["message"], state)
            save_state(state)
        time.sleep(1)


if __name__ == "__main__":
    main()
