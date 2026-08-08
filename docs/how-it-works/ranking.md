---
icon: lucide/list-ordered
---

# Ranking

Ranking has two layers.

`src/casita/rank.py` is the deterministic sorter. It handles explicit pipeline
state, votes, filtered listings, and heuristic score. Human engagement beats a
fresh LLM rank because an active conversation is real work.

`src/casita/llm.py` is the preference ranker. `rank_listings` builds a compact
brief for each listing, adds route summaries, attaches current feedback, and
asks Gemini to return every listing with:

- a rank
- a one-sentence reason
- a severity: `ok`, `concerns`, or `filtered`

The ranking policy keeps the personal assumptions: large dogs, SF walkability,
Marin drive context, trail or beach access, and practical livability.

## Reading A Score

`score()` returns one integer, which cannot say whether a listing lost a point
or was never measured on that term. `score_detail()` returns the same total
plus three lists — `considered`, `unknown`, and `unscored` — and `casita why`
renders them:

```bash
uv run casita why                    # coverage across every active listing
uv run casita why --listing <slug>   # one listing, broken apart
uv run casita why --no-walk          # the score without the route matrix
```

It opens with `TERM_WEIGHTS`, ordered by how far each term can move a score, so
the policy's shape is legible before any listing is ranked. A reader whose life
does not match the heaviest terms can see that immediately rather than infer it
from a ranking.

The totals are unchanged: `score_detail(...).total` equals `score(...)` for
every fixture listing, with and without routes.

## Ways This Could Go Further

Ranking is deliberately still prompt-centric and Vertex-only. A future version
could make policy changes easier to evaluate, compare deterministic and LLM
rank movement, or support another model backend.
