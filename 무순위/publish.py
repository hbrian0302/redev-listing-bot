#!/usr/bin/env python3
"""승인 무순위 카드(3장) → 스레드 발행. approved → published.
사용: python publish.py [--count 1] [--dry-run] [--now]  세션: ~/.threads_redev_session.json"""
from __future__ import annotations
import asyncio, json, random, sys, time
from pathlib import Path
import httpx

BASE = Path(__file__).resolve().parent
Q = BASE / "queue"; APPROVED, PUBLISHED = Q / "approved", Q / "published"
PUBLISHED.mkdir(parents=True, exist_ok=True)
EXPIRED = Q / "expired"; EXPIRED.mkdir(parents=True, exist_ok=True)
SESSION = str(Path.home() / ".threads_redev_session.json")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
URL = "https://www.threads.com/"


def _tg():
    tok = None
    try:
        import keyring; tok = keyring.get_password("redev_market", "review_bot_token")
    except Exception:
        pass
    chat = None
    envf = Path.home() / "agents/telegram-claude/.env"
    if envf.exists():
        for l in envf.read_text().splitlines():
            if l.strip().startswith("ALLOWED_USER_ID="):
                chat = l.split("=", 1)[1].strip().strip('"').strip("'")
    return tok, chat

def notify(text):
    tok, chat = _tg()
    if tok and chat:
        try:
            httpx.post(f"https://api.telegram.org/bot{tok}/sendMessage",
                       data={"chat_id": chat, "text": text}, timeout=30)
        except Exception:
            pass

def is_expired(item: dict, today=None) -> bool:
    """접수 마감이 지났는가. 마감일 정보가 없으면 만료로 보지 않는다."""
    import datetime
    end = item.get("rcept_end")
    if not end:
        return False
    today = today or datetime.date.today()
    try:
        return datetime.date.fromisoformat(end) < today
    except ValueError:
        return False


def sort_by_deadline(items: list[dict], today=None, drop_expired: bool = False) -> list[dict]:
    """접수 마감 임박순 정렬. 마감일 없는 건은 뒤로. drop_expired면 만료분 제외."""
    if drop_expired:
        items = [i for i in items if not is_expired(i, today)]
    return sorted(items, key=lambda i: (i.get("rcept_end") is None, i.get("rcept_end") or ""))


def urgent_approved(n):
    """승인 큐를 마감 임박순으로. 만료분은 queue/expired로 옮기고 후보에서 뺀다."""
    loaded = []
    for f in APPROVED.glob("*.json"):
        try:
            d = json.loads(f.read_text())
        except Exception:
            continue
        d["_path"] = f
        loaded.append(d)
    for d in loaded:
        if is_expired(d):
            p = d["_path"]
            p.rename(EXPIRED / p.name)
            notify(f"🗑 접수 마감 경과로 폐기: {d.get('house_nm', p.stem)}")
            print(f"  🗑 만료 폐기 {p.stem}")
    alive = sort_by_deadline([d for d in loaded if not is_expired(d)])
    return [d["_path"] for d in alive[:n]]


async def post_one(pg, d, dry):
    await pg.goto(URL, wait_until="domcontentloaded", timeout=30000)
    await pg.wait_for_timeout(3000)
    await pg.click('svg[aria-label="만들기"]', timeout=15000)
    await pg.wait_for_timeout(2500)
    ce = pg.locator('[contenteditable="true"]').first
    await ce.click()
    await pg.keyboard.insert_text(d.get("caption_threads") or d.get("caption", ""))
    await pg.wait_for_timeout(800)
    await pg.keyboard.press("Escape")   # @멘션 자동완성 닫기
    await pg.wait_for_timeout(600)
    imgs = d.get("images", [])
    if imgs:
        await pg.locator('input[type="file"]').first.set_input_files([str(p) for p in imgs])
        await pg.wait_for_timeout(2500 + 1500 * len(imgs))
    if dry:
        print(f"  [dry] {d.get('listing_id')} 작성만"); return False
    await pg.get_by_role("button", name="게시", exact=True).last.click(timeout=15000)
    await pg.wait_for_timeout(6000)
    return True


async def main():
    args = sys.argv[1:]; dry = "--dry-run" in args
    count = int(args[args.index("--count") + 1]) if "--count" in args else 1
    if not dry and "--now" not in args:
        jit = random.randint(0, 1200); print(f"⏳ 지터 {jit}s"); time.sleep(jit)
    if not Path(SESSION).exists():
        print(f"세션 없음: {SESSION}"); return
    targets = urgent_approved(count)
    if not targets:
        print("발행할 승인 카드 없음"); return
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(storage_state=SESSION, user_agent=UA,
                                  viewport={"width": 1300, "height": 950}, locale="ko-KR")
        pg = await ctx.new_page()
        try:
            for f in targets:
                d = json.loads(f.read_text())
                nm = f"{d['data'].get('name_l1','')} {d['data'].get('name_l2','')}"
                try:
                    t_ok = await post_one(pg, d, dry)
                    if t_ok:
                        d["published_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                        (PUBLISHED / f.name).write_text(json.dumps(d, ensure_ascii=False, indent=2))
                        f.unlink()
                        notify(f"✅ 발행 [스레드] {nm}")
                        for img in d.get("images", []):
                            try: Path(img).unlink()
                            except Exception: pass
                        print(f"  ✅ 발행 {f.stem} (스레드)")
                except Exception as e:
                    print(f"  ! {f.stem} 실패(approved 유지): {e}")
                    notify(f"❌ 발행 실패 {nm}: {e}")
        finally:
            await b.close()


if __name__ == "__main__":
    asyncio.run(main())
