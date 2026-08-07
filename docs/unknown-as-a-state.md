# Unknown as a state

## What I changed

Casita reports *"we checked and found nothing"* and *"we could not check"* with
the same words. I made the difference visible in the two places where it
changes what a person would do next: the preference audit, and the heuristic
score.

Nothing about the ranking arithmetic moved. Every listing scores exactly what
it scored before.

## Why this and not something else

`docs/architecture.md` lists real rough edges, and the ranking page has a "Ways
This Could Go Further" note. Picking from either would have told you I can read
a to-do list.

I went looking instead for the place where the system is *confidently wrong*
rather than openly incomplete — a bug the documentation cannot warn you about,
because the documentation does not know it is there.

Two things I reproduced, in order of how much they worried me.

## 1. The audit tool denies its own evidence

`casita analyze-prefs` is the feedback loop described in
`docs/how-it-works/learning.md`. On the shipped demo fixture, with no Vertex
credentials:

```
  llm config err: Set CASITA_GCP_PROJECT to use Vertex-backed LLM commands.
no votes with reasons yet — nothing to analyze.
```

The fixture holds 34 written reasons: 16 votes and 18 pass notes. The tool
never read one of them, then reported that none exist. The warning line above
the conclusion is real, but the conclusion contradicts it, and the command
**exits 0** — so anything reading the exit status sees success.

This is the case that decided the submission for me. Every reader without
credentials runs this command, sees "no votes", and concludes the learning loop
is empty. It is not empty. It is *unreachable*, which is a different problem
with a different fix, and the tool is actively steering people to the wrong
one.

### The cause

`_call_structured` collapsed four outcomes into a single `None`:

| stage | what happened |
| --- | --- |
| `config` | no credentials configured; nothing was sent |
| `call` | the request was sent and the API failed |
| `empty` | the model answered with nothing |
| `parse` | the model answered, but not in the shape we asked for |

`analyze_preferences` then returned `None` for a fifth reason — genuinely
having no votes. The CLI received one `None`, had to guess which of the five it
meant, and guessed the reassuring one.

### The fix

`_call_structured_strict` raises `LLMUnavailable` carrying the stage it failed
at, and `analyze_preferences` attaches the row count on the way out, because
"34 votes, unread" is a very different line than "0 votes". The same command
now prints:

```
could not audit the policy — 34 votes with reasons went unread.
no Vertex credentials configured, so nothing was ever sent: Set CASITA_GCP_PROJECT ...
this is not a finding about your votes. nothing was analyzed.
```

and exits 1.

The lenient `_call_structured` still returns `None`. The other four call sites
enrich one listing at a time and skip on failure, which is correct behavior and
does not need the distinction. Migrating them would have been change without a
reason.

## 2. A score cannot say which kind of zero it is

`rank.score` returns one integer. A missing laundry field and an apartment with
no laundry both contribute zero, and the integer cannot tell you which
happened.

`score_detail` returns the same total plus three lists:

- `considered` — the policy has an opinion and the listing had the data
- `unknown` — the policy has an opinion and the listing had no data
- `unscored` — the listing has the data and the policy has no opinion

Running it across the fixture, which is the first thing I did after it worked:

```
143 active listings — 702 of 885 scoring terms informed, 183 unmeasured

most common gaps
  parking              missing on 75 of 143 listings
  laundry              missing on 73 of 143 listings
  bathrooms            missing on 17 of 143 listings
  bedrooms             missing on 16 of 143 listings
```

Over half the listings are being scored on parking and laundry they never
reported. That was invisible before. It is not a bug in the scraper or the
ranker — it is a fact about the data that the score had no way to express.

### A gate is the least examined score of all

The dog gate returns -1000 immediately. In the sorted output a gated listing
looks like the most thoroughly rejected item on the page. It is the opposite:
it is the one the system knows the least about.

```
zumper:63357941 — $4,500 · Central Richmond
score -1000 · gated on dog policy — no other term was evaluated

measured
  dog policy           -1000

scoring stopped at the dog policy gate
  beds, baths, laundry, parking and walk times were never evaluated for this listing

not a term in this policy
  rent
  square footage
```

The last block is the part I would want if this were my search. Rent is on
every listing and is not a term in this policy, so a $1,800 and a $9,000
apartment tie.

## What I deliberately did not change

Both of those are assumptions, not bugs. The policy is built around one
household — two large dogs, the Presidio, walkability — and `docs/index.md`
says so on purpose. A cat-only listing scoring -1000 is correct for the author
and wrong for a reader in a different situation, and rent being absent from the
scorer is a real choice about what this tool is for.

I did not touch either one. Showing an assumption and overruling it are
different acts, and in someone else's repo only the first is mine to do. The
version of this change that "fixes" the gate is the version you would have to
undo.

I also left these out on purpose:

- **Surfacing coverage in the rendered site.** It belongs there more than in a
  CLI. The honest version needs a design decision about the card layout, and
  guessing at that produces the kind of change you have to revert.
- **Pointing `analyze-prefs` at `rank.py`.** The audit reads the LLM policy in
  `_RANK_SYSTEM` and never sees the heuristic. Now that `score_detail` reports
  its own blind spots, feeding those to the audit is a natural next step — and
  a larger one than it looks.

## What I checked before claiming any of it

Score equivalence is the risk in this change, so I verified it instead of
asserting it. `score_detail(...).total` equals `score(...)` for all 143 fixture
listings, with and without the route matrix: **286 comparisons, zero
differences.**
`test_score_detail_totals_match_score_across_the_fixture` keeps that honest
going forward, and I confirmed the test earns its keep by changing one weight
in `score_detail` and watching it fail.

`make check` passes: 31 tests, the public leak validator, the docs build, the
package build, and the CLI import. Every command block in this document and in
the README was re-run on a clean checkout with no `.env` and no credentials,
and pasted from its output.

The exit codes are part of the fix. `analyze-prefs` exits 1 when it could not
audit, rather than 0. Anything reading the status now sees the failure that the
text describes.

## The principle

`docs/how-it-works/learning.md` says a revealed preference should become policy
through an intentional code change, rather than the system quietly adjusting
itself. That is a statement about trust: you should be able to see what the
system concluded, and disagree with it.

The same standard applies to what the system did *not* conclude. An answer you
cannot audit and an answer that was never computed are equally unarguable, and
until now they were printed identically.
