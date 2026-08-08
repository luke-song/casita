---
icon: lucide/thumbs-up
---

# Learning From Votes

The feedback loop lives in `src/casita/llm.py` and the CLI in
`src/casita/__init__.py`.

Votes and pass reasons are stored in SQLite. During ranking, Casita builds:

- inline feedback for listings in the current batch
- a capped few-shot block of recent up/pass examples
- an audit prompt exposed through `casita analyze-prefs`

`analyze-prefs` reads the votes and compares revealed preference against the
static ranking policy. It proposes contradictions and new rules, but it never
edits code. A human decides whether a proposed rule belongs in the prompt.

### When it cannot read them

The audit depends on a model call, and that call can fail in four ways: no
credentials configured, the API rejecting the request, an empty response, and a
response that fails schema validation. None of those mean "there are no votes",
so the command does not say so.

`_call_structured_strict` raises `LLMUnavailable` carrying the stage it failed
at, and `analyze_preferences` attaches how many rows were waiting on the answer:

```
could not audit the policy — 34 votes with reasons went unread.
no Vertex credentials configured, so nothing was ever sent: Set CASITA_GCP_PROJECT ...
this is not a finding about your votes. nothing was analyzed.
```

It exits non-zero, so a script reading the status sees the failure the text
describes. `no votes with reasons yet` is now reserved for the one case where
it is true: the query came back empty.

The lenient `_call_structured` still returns `None`, because the per-listing
enrichment callers skip on failure and cannot act on the distinction.

## Ways This Could Go Further

The loop could gain better fixtures, better diff output, or clearer aging of
old examples. The important property to preserve is reviewability: revealed
preference should become policy through an intentional code change.
