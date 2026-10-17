#!/usr/bin/env python3
"""재개발 매물 카드 검수 봇. queue/pending → 텔레그램(카드 다장+캡션) → 승인/반려/수정.
승인분은 queue/approved 로 이동(발행 단계가 가져감). 떠리마켓 review_bot 패턴."""
from __future__ import annotations
import json, sys, time
from pathlib import Path
import httpx
sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import DB

BASE = Path(__file__).resolve().parent
FALLBACK_ENV = Path.home() / "agents/telegram-claude/.env"
Q = BASE / "queue"
PENDING, APPROVED, REJECTED = Q / "pending", Q / "approved", Q / "rejected"
STATE = Q / "_review_state.json"
for d in (PENDING, APPROVED, REJECTED):
    d.mkdir(parents=True, exist_ok=True)
KEYRING_SERVICE = "redev_market"


def _load_env(p: Path) -> dict:
    e = {}
    if p.exists():
        for l in p.read_text().splitlines():
            l = l.strip()
            if l and not l.startswith("#") and "=" in l:
                k, v = l.split("=", 1); e[k.strip()] = v.strip().strip('"').strip("'")
    return e


def _keyring(key):
    try:
        import keyring
        return keyring.get_password(KEYRING_SERVICE, key)
    except Exception:
        return None


TOKEN = _keyring("review_bot_token")
CHAT = _keyring("review_chat_id") or _load_env(FALLBACK_ENV).get("ALLOWED_USER_ID")
API = f"https://api.telegram.org/bot{TOKEN}"


def load_state():
    s = json.loads(STATE.read_text()) if STATE.exists() else {}
    s.setdefault("sent", {}); s.setdefault("offset", 0)
    s.setdefault("awaiting_edit", None); s.setdefault("awaiting_comment", None)
    return s


def save_state(s):
    STATE.write_text(json.dumps(s, ensure_ascii=False, indent=2))


def keyboard(code):
    return {"inline_keyboard": [
        [{"text": "✅ 승인", "callback_data": f"ok:{code}"},
         {"text": "✍️ 한마디", "callback_data": f"cm:{code}"}],
        [{"text": "✏️ 캡션수정", "callback_data": f"ed:{code}"},
         {"text": "❌ 반려", "callback_data": f"no:{code}"}]]}


def api(method, **kw):
    try:
        return httpx.post(f"{API}/{method}", json=kw, timeout=60).json()
    except Exception as e:
        print("api err", method, e); return {"ok": False}


def send_cards(images: list[str], caption: str, kb: dict):
    """다장이면 sendMediaGroup(캡션은 첫 장) 후 버튼 메시지 별도, 1장이면 sendPhoto+버튼."""
    if len(images) == 1:
        with open(images[0], "rb") as f:
            r = httpx.post(f"{API}/sendPhoto",
                           data={"chat_id": str(CHAT), "caption": caption[:1024],
                                 "reply_markup": json.dumps(kb)},
                           files={"photo": ("c.png", f, "image/png")}, timeout=90)
        return r.json()
    media, files, handles = [], {}, []
    try:
        for i, p in enumerate(images):
            fh = open(p, "rb")
            handles.append(fh)
            files[f"f{i}"] = (f"c{i}.png", fh, "image/png")
            item = {"type": "photo", "media": f"attach://f{i}"}
            if i == 0:
                item["caption"] = caption[:1024]
            media.append(item)
        httpx.post(f"{API}/sendMediaGroup",
                   data={"chat_id": str(CHAT), "media": json.dumps(media)},
                   files=files, timeout=120)
    finally:
        for fh in handles:
            fh.close()
    return api("sendMessage", chat_id=CHAT, text="↑ 위 카드 검수", reply_markup=kb)


def push_new(state):
    for f in sorted(PENDING.glob("*.json")):
        code = f.stem
        if code in state["sent"]:
            continue
        d = json.loads(f.read_text())
        res = send_cards(d["images"], d.get("caption", ""), keyboard(code))
        if res.get("ok"):
            state["sent"][code] = res["result"]["message_id"]
            print(f"→ 검수 전송: {code}"); save_state(state)


def move(code, dest, patch=None):
    src = PENDING / f"{code}.json"
    if not src.exists():
        return None
    d = json.loads(src.read_text())
    if patch:
        d.update(patch)
    (dest / f"{code}.json").write_text(json.dumps(d, ensure_ascii=False, indent=2))
    src.unlink()
    return d


def handle_callback(cb, state, db):
    data = cb.get("data", "")
    mid = cb.get("message", {}).get("message_id")
    cid = cb.get("message", {}).get("chat", {}).get("id")
    api("answerCallbackQuery", callback_query_id=cb["id"])
    if ":" not in data:
        return
    action, code = data.split(":", 1)
    if action == "ok":
        d = move(code, APPROVED)
        if d and d.get("listing_id") is not None:
            db.set_status(d["listing_id"], "approved")
        api("editMessageReplyMarkup", chat_id=cid, message_id=mid,
            reply_markup={"inline_keyboard": [[{"text": "✅ 승인됨 — 발행 대기", "callback_data": "x"}]]})
    elif action == "no":
        d = move(code, REJECTED)
        if d and d.get("listing_id") is not None:
            db.set_status(d["listing_id"], "rejected")
        for img in (d or {}).get("images", []):      # 반려 카드 PNG 고아 정리
            try:
                Path(img).unlink()
            except Exception:
                pass
        api("editMessageReplyMarkup", chat_id=cid, message_id=mid,
            reply_markup={"inline_keyboard": [[{"text": "❌ 반려됨", "callback_data": "x"}]]})
    elif action == "ed":
        state["awaiting_edit"] = code; save_state(state)
        api("sendMessage", chat_id=cid,
            text=f"✏️ '{code}' 새 캡션을 답장으로 보내주세요(그대로 승인).")
    elif action == "cm":
        state["awaiting_comment"] = code; save_state(state)
        api("sendMessage", chat_id=cid,
            text=f"✍️ '{code}'에 넣을 재미나이 한마디를 답장으로 보내주세요.\n"
                 "(카드 3페이지에 '— 재미나이' 서명으로 박혀서 나갑니다. 아는 구역 실경험 한 줄이면 딱)")


def add_comment_rerender(code: str, comment: str):
    """재미나이 한마디를 카드에 넣어 재렌더. 성공 시 갱신 draft, 실패 시 None."""
    src = PENDING / f"{code}.json"
    if not src.exists():
        return None
    d = json.loads(src.read_text())
    data = dict(d.get("data", {}))
    data["founder_note"] = comment.strip()
    try:
        import asyncio
        from render import render_card
        from mapgen import static_map_datauri
        data["map_img"] = static_map_datauri(data.get("location") or data.get("zone", ""))
        for img in d.get("images", []):        # 기존 PNG 제거 후 재렌더
            try:
                Path(img).unlink()
            except Exception:
                pass
        stem = str(data.get("listing_id") or code)
        paths = asyncio.run(render_card(data, PENDING, stem))
    except Exception as e:
        print("re-render 실패:", e)
        return None
    data.pop("map_img", None)               # JSON엔 대용량 base64 제외
    d["data"] = data
    d["images"] = [str(p) for p in paths]
    src.write_text(json.dumps(d, ensure_ascii=False, indent=2))
    return d


def handle_message(m, state, db):
    text = (m.get("text") or "").strip()
    cid = m["chat"]["id"]
    ccode = state.get("awaiting_comment")
    if ccode:
        state["awaiting_comment"] = None; save_state(state)
        if not text:
            return
        d = add_comment_rerender(ccode, text)
        if d:
            state["sent"].pop(ccode, None); save_state(state)   # push_new가 갱신 카드 재전송
            api("sendMessage", chat_id=cid, text=f"✍️ '{ccode}' 한마디 반영 — 카드 다시 보냅니다. 확인 후 승인.")
        else:
            api("sendMessage", chat_id=cid, text=f"⚠️ '{ccode}' 반영 실패(큐에 없거나 렌더 오류).")
        return
    code = state.get("awaiting_edit")
    if not code:
        return
    if not text:
        return
    d = move(code, APPROVED, {"caption": text, "edited": True})
    if d and d.get("listing_id") is not None:
        db.set_status(d["listing_id"], "approved")
    state["awaiting_edit"] = None; save_state(state)
    api("sendMessage", chat_id=cid, text=f"✏️→✅ '{code}' 수정 캡션으로 승인.")


def main():
    assert TOKEN, "봇 토큰 없음 — keyring redev_market/review_bot_token 등록 필요"
    assert CHAT, "chat id 없음 — telegram-claude .env ALLOWED_USER_ID 확인"
    db = DB()
    state = load_state()
    api("sendMessage", chat_id=CHAT, text="🟢 재개발 매물 검수 봇 시작.")
    print(f"● 검수 봇 (chat={CHAT})")
    while True:
        push_new(state)
        for up in api("getUpdates", offset=state["offset"], timeout=30).get("result", []):
            state["offset"] = up["update_id"] + 1
            if "callback_query" in up:
                handle_callback(up["callback_query"], state, db)
            elif "message" in up:
                handle_message(up["message"], state, db)
            save_state(state)
        time.sleep(1)


if __name__ == "__main__":
    main()
