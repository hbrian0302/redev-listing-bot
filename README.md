# redev-listing-bot

An LLM content pipeline for Korean real-estate listings that **cannot invent numbers**, and where **a human approves every post** before it goes out.

한국 부동산(무순위 청약·재개발 매물) 정보를 공공데이터로 분석해 카드뉴스와 캡션을 만들고, LLM이 숫자를 지어내지 못하게 코드로 막은 뒤, 사람이 검수·승인해야만 발행되는 반자동 파이프라인입니다.

## The problem it solves

LLM-written captions about money are dangerous: one wrong price or deadline and a reader acts on false information. This project treats that as an engineering problem, not a prompting problem.

```
data.go.kr announcements ──▶ margin & location score ──▶ decision
                                                            │
        human approves in Telegram ◀── card images ◀── caption (LLM)
                  │                                          ▲
                  ▼                                          │
          publish to Threads              fact whitelist + violation check
                                          (retry ×2, then deterministic fallback)
```

### 1. Fact whitelist + no-fabrication validator (`무순위/caption.py`)

- `build_facts()` is the only source of numbers the LLM may use (price, market price, margin, dates, days left).
- `violations()` parses the generated caption with regexes and rejects any amount, date or "D-N" that is not in the whitelist. It understands `6.46억`, `6억 4600만원` and `5000만원`, and avoids false positives such as `30만 명`.
- On violation the caption is regenerated up to twice with the offending values fed back; if it still fails, a template caption is used. A bad number never reaches the reviewer.

### 2. Decisions from absolute margin, not percentages (`무순위/margin.py`)

The first version graded listings by percentage below market. Measured against 326 real announcements, that was wrong: a 15%-cheaper ₩500M complex is only a ₩75M margin but was promoted to "must apply", while a 5%-cheaper ₩3B complex (₩150M margin) was demoted. The v2 design (`무순위/docs/superpowers/specs/`) records the measurement, the rejected hypotheses, and the fix: an absolute-margin ladder, a ratio guard that takes the lower grade on conflict, and a confidence guard for thin comparison samples.

### 3. Human-in-the-loop queue

`pending → approved → published` is a file queue. A Telegram bot shows the cards and caption; nothing is published without approval. The approved queue is sorted by application deadline and expired items are dropped automatically.

## Layout

| Path | What it does |
|---|---|
| `무순위/` | Unranked-lottery (무순위) apartment bot: public-data API → margin → 100-point location score (OSM distances) → 3 dark cards → caption → review → Threads |
| `pipeline/` | Blog-listing bot: crawl partner brokers' blogs → LLM classify & extract → card → review → publish |

Both call Claude through the Claude Code CLI (`claude -p`).

## Tests

```bash
pip install -r requirements.txt pytest
cd 무순위 && python -m pytest        # 69 tests
cd .. && python -m pytest pipeline   # 34 tests
```

The tests need no API keys, browser or Claude CLI; the LLM is injected as a function, so the caption guard is tested with fake model outputs.

## Running it for real

Secrets are never stored in this repo. They are read from the macOS keychain (service `redev_market`): the data.go.kr key, Naver Cloud map keys, and the Telegram review-bot token. Scheduling uses macOS `launchd` (see `launchd/*.plist`; replace `/path/to/repo` and `/Users/USER`). Details for the blog pipeline are in `pipeline/README.md` (Korean).

## Status and honesty notes

- The unranked-lottery bot ran live but got almost no engagement. The v2 spec diagnoses why (a percentage-based filter was publishing low-value listings and captions had no deadline) and the changes above are the response. Whether v2 raises engagement has not been measured yet.
- Market prices are estimated from nearby actual-transaction records, so the margin is an estimate, not a guarantee. The pipeline marks low-sample cases and keeps them out of the feed.
- Built for macOS and Python 3.9+. Korean comments and prompts throughout.
