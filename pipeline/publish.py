#!/usr/bin/env python3
"""승인 매물 카드를 스레드(재개발 계정)로 발행. approved → published.
사용: uv run python publish.py [--count 1] [--dry-run] [--now]
세션: ~/.threads_redev_session.json"""
from __future__ import annotations
import asyncio, json, random, sys, time
from pathlib import Path
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import DB

BASE = Path(__file__).resolve().parent
Q = BASE / "queue"
APPROVED, PUBLISHED = Q / "approved", Q / "published"
APPROVED.mkdir(parents=True, exist_ok=True)
PUBLISHED.mkdir(parents=True, exist_ok=True)
SHOTS = BASE / "publish_shots"; SHOTS.mkdir(exist_ok=True)
SESSION = str(Path.home() / ".threads_redev_session.json")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
URL = "https://www.threads.com/"
KEYRING_SERVICE = "redev_market"


def _tg():
    tok = None
    try:
        import keyring; tok = keyring.get_password(KEYRING_SERVICE, "review_bot_token")
    except Exception:
        pass
    chat = None
    envf = Path.home() / "agents/telegram-claude/.env"
    if envf.exists():
        for l in envf.read_text().splitlines():
            if l.strip().startswith("ALLOWED_USER_ID="):
                chat = l.split("=", 1)[1].strip().strip('"').strip("'")
    return tok, chat


def notify(text, photo=None):
    tok, chat = _tg()
    if not (tok and chat):
        return
    try:
        if photo:
            with open(photo, "rb") as f:
                httpx.post(f"https://api.telegram.org/bot{tok}/sendPhoto",
                           data={"chat_id": chat, "caption": text[:1024]},
                           files={"photo": ("p.png", f, "image/png")}, timeout=60)
        else:
            httpx.post(f"https://api.telegram.org/bot{tok}/sendMessage",
                       data={"chat_id": chat, "text": text}, timeout=30)
    except Exception as e:
        print("tg err", e)


def oldest_approved(n):
    fs = sorted(APPROVED.glob("*.json"), key=lambda f: f.stat().st_mtime)
    return fs[:n]


async def post_one(pg, d, dry):
    await pg.goto(URL, wait_until="domcontentloaded", timeout=30000)
    await pg.wait_for_timeout(3000)
    await pg.click('svg[aria-label="만들기"]', timeout=15000)
    await pg.wait_for_timeout(2500)
    ce = pg.locator('[contenteditable="true"]').first
    await ce.click()
    await pg.keyboard.insert_text(d.get("caption", ""))
    await pg.wait_for_timeout(800)
    imgs = d.get("images", [])
    if imgs:
        await pg.locator('input[type="file"]').first.set_input_files([str(p) for p in imgs])
        await pg.wait_for_timeout(2000 + 1500 * len(imgs))   # 다장 업로드 대기
    code = d.get("listing_id") or (Path(d["images"][0]).stem if d.get("images") else "unknown")
    await pg.screenshot(path=str(SHOTS / f"{code}_compose.png"))
    if dry:
        print(f"  [dry] {code} 작성만(게시 안 함)"); return False
    await pg.get_by_role("button", name="게시", exact=True).last.click(timeout=15000)
    await pg.wait_for_timeout(6000)
    return True


async def main():
    args = sys.argv[1:]
    dry = "--dry-run" in args
    count = int(args[args.index("--count") + 1]) if "--count" in args else 1
    if not dry and "--now" not in args:
        jit = random.randint(0, 1200)
        print(f"⏳ 지터 {jit}s"); time.sleep(jit)
    if not Path(SESSION).exists():
        print(f"세션 없음: {SESSION}"); return
    targets = oldest_approved(count)
    if not targets:
        print("발행할 승인 매물 없음"); return
    db = DB()
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(storage_state=SESSION, user_agent=UA,
                                  viewport={"width": 1280, "height": 900}, locale="ko-KR")
        pg = await ctx.new_page()
        try:
            for f in targets:
                d = json.loads(f.read_text())
                try:
                    ok = await post_one(pg, d, dry)
                    if ok:
                        d["published_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                        (PUBLISHED / f.name).write_text(json.dumps(d, ensure_ascii=False, indent=2))
                        f.unlink()
                        notify(f"✅ 스레드 발행 [{time.strftime('%H:%M')}]\n{d['data'].get('zone','')}",
                               photo=d["images"][0])
                        print(f"  ✅ 발행: {f.stem}")
                        if d.get("listing_id") is not None:
                            db.set_status(d["listing_id"], "published")
                        for img in d.get("images", []):     # 발행 끝난 카드 PNG 정리
                            try:
                                Path(img).unlink()
                            except Exception:
                                pass
                except Exception as e:
                    print(f"  ! {f.stem} 발행 실패(approved 유지): {e}")
                    notify(f"❌ 발행 실패 — {f.stem}: {e}")
        finally:
            await b.close()


if __name__ == "__main__":
    asyncio.run(main())
