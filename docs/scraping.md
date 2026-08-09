---
icon: lucide/search
---

# Scraping

The offline demo needs none of this. `casita demo` renders the fixture.

Live scraping uses Playwright:

- Zillow: `src/casita/zillow.py`
- Craigslist: `src/casita/craigslist.py`
- Zumper: `src/casita/zumper.py`
- Redfin: `src/casita/redfin.py`

Zillow and Redfin can trigger PerimeterX. The human-in-the-loop path is:

```bash
uv run casita solve
uv run casita search --headed
```

`solve` opens a headed browser at Zillow. You clear the captcha manually, then
the session persists in `.chrome-profile/`. Later headed searches reuse that
profile. Craigslist, Zumper, and Redfin have their own source-specific parsing
paths.

## Blocked Is Not Empty

Each source searches several areas — Zillow and Zumper eight neighborhoods
each, Redfin three regions, Craigslist two queries. A bot wall stops one area
at a time, and a stopped area used to return `[]`, which is also what an area
with no matching listings returns.

That difference reaches further than the run log. `search` passes
`succeeded_sources` to `storage.upsert_run`, which marks a listing inactive
when its source reported in and did not mention it. The guard was per source
while the blocking is per area, so one readable area was enough to delist every
listing in the areas nobody could open — not because they left the market, but
because nobody could look.

`scrape()` now raises `SourceUnavailable` carrying the area and how far the
fetch got (`load`, `blocked`, `parse`). `scrape_all()` returns a
`ScrapeOutcome` holding the listings alongside which areas were read and which
were not, and only a source with full coverage is allowed to delist:

```
  zillow: 41 listings from 6 of 8 areas — 2 unread: outer-sunset (blocked), lake-street (load)
  zillow: not delisting — 2 area(s) went unread this run
```

A partial run still contributes everything it found. It just cannot claim that
what it did not see is gone.

## Ways This Could Go Further

Scraping could gain better source isolation, clearer retry reporting, richer
fixtures, or tests around parser behavior. The current code preserves the
human-in-the-loop reality instead of pretending the live scrape is fully
unattended.
