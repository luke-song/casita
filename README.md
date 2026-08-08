# Casita

[![Documentation](https://img.shields.io/badge/docs-casita-0b6e4f?style=for-the-badge)](https://matin.github.io/casita/)

Casita is a personal rental-search tool published as a public repo.

It started as a small script for a time-boxed San Francisco rental search with
two large dogs: scrape Zillow, Craigslist, Zumper, and Redfin; enrich the
listings; rank them; and render a static page that was easier to review than
four open browser tabs.

This is not a product or service. It is published as-is, under MIT, as a
personal-use codebase for an interview loop. The interesting part is what a
candidate chooses to improve.

## Why I chose this (fork note)

I started by trying to use it. I have a cat, not two large dogs. I live in San
Jose, I drive, and I care about EV charging. So before I had read much of the
code I went to point this at my own search, and everything below came out of
that.

Pointing it at my life meant editing it. The household is not configuration
here, it is literals — the gate in `rank.py`, the neighborhood lists in
`locations.py`, the ranking policy in `llm.py`. That is a real cost. It is also
the reason the tool is worth anything: *walk to the Presidio, weighted ×2* is a
judgment someone made about their own life, and no rental site is going to tell
you that.

What I did not expect was how the result read. The ranking came out looking
reasonable, and it should not have. The two heaviest terms in this policy are
`walk to Presidio` (×2) and `walk to beach`. I do not walk to either one. The
tool scored me anyway, and nothing in the output said that what it was
measuring was not what I was asking about.

So I built a preferences system — pet, budget, city, all of it configurable —
and then I deleted it.

Two things killed it. It silently changed 106 of 143 fixture scores while
reporting nothing unusual, which is the same bug I had come to fix, committed
by my own diff. And it was not worth its cost: forking this repo and telling a
coding agent to make it about a cat and a $4,000 cap takes minutes. A
configuration layer buys those minutes back and spends the thing that makes
this tool good. Turn *×2 for the Presidio* into a slider and you have built a
filter panel.

What I needed was not flexibility. It was for the tool to say what it knows.

`casita analyze-prefs` reads every vote and pass note and reports where the
policy contradicts the reviewer's actual behavior. On the shipped fixture, with
no credentials:

```
  llm config err: Set CASITA_GCP_PROJECT to use Vertex-backed LLM commands.
no votes with reasons yet — nothing to analyze.
```

**The fixture holds 34 written reasons.** It read none of them, reported that
none exist, and exited 0. Everyone who clones this without Vertex credentials
hits that line and concludes the feedback loop is empty. It is not empty. It is
unreachable, and those two need different fixes.

The score has the same shape of problem one layer down. A missing laundry field
and an apartment with no laundry both contribute zero. On this fixture parking
goes unreported on 75 of 143 listings and laundry on 73 — over half the page is
scored on facts the listings never stated. Nobody chose to ignore that; the
number had no way to express it.

That matters more here than it would in most tools, because the output is a
list of places a person might live. A score built on facts that were never
checked sends someone to spend a Saturday on the wrong apartment, or past the
right one.

### What I did not change

`casita why` surfaced two assumptions that are wrong for me and right for this
repo. Rent is not a term in the policy, so $1,800 and $9,000 can tie. The gate
is written for two large dogs, so a cat-only listing takes -1000 and stops being
scored at all. Both are correct for a tool built around one household's search,
and `docs/index.md` says so.

Showing an assumption and overruling it are different acts, and in someone
else's repo only the first one is mine to do. The version of this change that
"fixes" the gate is the version you would have to undo.

So the arithmetic does not move. Every listing scores exactly what it scored
before — 143 listings, with and without the route matrix, 286 comparisons, zero
differences.

Start with `uv run casita why`.
**[The full reasoning: docs/unknown-as-a-state.md](docs/unknown-as-a-state.md)**

## Demo

The demo is credentials-free and uses a sanitized SQLite fixture with cached
route times and precomputed LLM enrichment.

```bash
uv sync
uv run playwright install chromium
uv run casita demo
```

Then open <http://127.0.0.1:8765/>.

The demo does not scrape, call Vertex, deploy to Firebase, read GCS, or call the
Google Maps Routes API. It does use Playwright's local Chromium browser to
render Open Graph preview images from listing photos and facts. Live `search` /
`enrich` / `publish` paths still exist for private use and are controlled by
environment variables; see `.env.example`.

## What It Does

- Scrapes active rental listings from Zillow, Craigslist, Zumper, and Redfin.
- Normalizes listing facts into SQLite.
- Classifies dog policy and enriches details from listing pages.
- Uses Gemini for fact extraction, photo review, share blurbs, and ranking.
- Computes walking and driving times to curated SF / Marin anchors.
- Renders a static, mobile-friendly site with index and detail pages.
- Records votes and passes so future ranking can learn from reviewer feedback.

The domain assumptions are intentionally personal: large dogs, San Francisco
walkability, Marin driving context, trails, beaches, and good bakeries nearby.
That is the point of a personal tool.

## Docs

The [documentation site](https://matin.github.io/casita/) explains the systems
without turning them into assigned tasks. To run it locally instead:

```bash
uv run zensical serve
```

Start at `docs/index.md`, or run `uv run zensical build` to generate the site.

## Checks

```bash
make check
```

This compiles the Python modules, runs the pytest suite, runs the public leak
validator, builds the docs, builds the Python package artifacts, and checks
that the CLI imports.

## Contributing

Read `CONTRIBUTING.md`. The short version: fork the repo, pick something you
think makes Casita better, and explain why you chose it.
