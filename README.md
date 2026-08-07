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

Casita says *"we checked and found nothing"* and *"we could not check"* with
the same words. Those two sentences should send a reader in opposite
directions, and right now they send them the same way.

`casita analyze-prefs` reads every vote and pass note, asks the model where the
ranking policy contradicts what the reviewer actually did, and prints the
contradictions. Run it on the shipped fixture with no credentials:

```
  llm config err: Set CASITA_GCP_PROJECT to use Vertex-backed LLM commands.
no votes with reasons yet — nothing to analyze.
```

**The fixture holds 34 written reasons.** The tool read none of them, reported
that none exist, and exited 0. Everyone who clones this repo without Vertex
credentials runs into that line and concludes the feedback loop is empty. It is
not empty. It is unreachable, and those two need different fixes.

The heuristic score has the same problem one layer down. A missing laundry
field and an apartment with no laundry both contribute zero, so the number
cannot say which happened. On this fixture, parking goes unreported on 75 of
143 listings and laundry on 73 — over half the page is scored on facts the
listings never stated, and nothing said so.

I picked this because it is the failure the docs could not warn me about.
`docs/architecture.md` already lists the rough edges; taking one of those would
only have shown that I can read a to-do list. This is where the system is
confidently wrong rather than openly incomplete.

### What I did not do

`casita why` surfaced two things that are wrong for me and right for this repo.
I left both alone.

Rent is not a term in the scoring policy, so a $1,800 and a $9,000 apartment
can tie. And the pet gate is written for two large dogs, so a cat-only listing
takes -1000 and stops being scored at all. Both are correct for a tool built
around one household's search, and `docs/index.md` says so plainly.

Showing an assumption and overruling it are different acts, and in someone
else's repo only the first one is mine to do. So the score reports them and
does not touch them: **every listing scores exactly what it scored before** —
143 listings, with and without the route matrix, 286 comparisons, zero
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
