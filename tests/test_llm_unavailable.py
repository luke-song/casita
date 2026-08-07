"""An answer we could not get is not an answer of "nothing".

`_call_structured` had four ways to fail and one way to say so: `None`.
`analyze_preferences` had a fifth `None` that meant something else entirely —
there were genuinely no votes. These tests hold those apart.
"""

import sqlite3

import pytest

from casita import llm


def _conn_with_reasons(n: int) -> sqlite3.Connection:
    """An in-memory DB shaped like the columns analyze_preferences reads."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE votes (id INTEGER PRIMARY KEY, listing_key TEXT, voter TEXT,
                            direction TEXT, reason TEXT, ts TIMESTAMP);
        CREATE TABLE listing_status (listing_key TEXT PRIMARY KEY, status TEXT,
                                     status_note TEXT, updated_at TIMESTAMP);
        CREATE TABLE actions (id INTEGER PRIMARY KEY, listing_key TEXT, voter TEXT,
                              kind TEXT, payload_json TEXT, ts TIMESTAMP);
        """
    )
    for i in range(n):
        conn.execute(
            "INSERT INTO votes (listing_key, voter, direction, reason, ts) VALUES (?,?,?,?,?)",
            (f"zillow:{i}", "reviewer", "up", f"reason {i}", f"2026-01-0{i % 9 + 1}"),
        )
    return conn


def test_llm_unavailable_carries_the_stage_and_the_count():
    e = llm.LLMUnavailable("config", "no project set", evidence=34)

    assert e.stage == "config"
    assert e.evidence == 34
    assert "config" in str(e)


def test_analyze_preferences_no_rows_returns_none():
    """The one honest None: nothing was written, so there is nothing to read."""
    conn = _conn_with_reasons(0)

    assert llm.analyze_preferences(conn) is None


def test_analyze_preferences_unreachable_model_raises_with_the_row_count(monkeypatch):
    """34 rows waiting on a call that never happened is not "no votes"."""
    conn = _conn_with_reasons(34)

    def _no_credentials(*args, **kwargs):
        raise llm.LLMUnavailable("config", "Set CASITA_GCP_PROJECT ...")

    monkeypatch.setattr(llm, "_call_structured_strict", _no_credentials)

    with pytest.raises(llm.LLMUnavailable) as excinfo:
        llm.analyze_preferences(conn)

    assert excinfo.value.stage == "config"
    assert excinfo.value.evidence == 34


@pytest.mark.parametrize("stage", ["config", "call", "empty", "parse"])
def test_analyze_preferences_every_failure_stage_survives_to_the_caller(monkeypatch, stage):
    """All four used to arrive as the same None. The caller reports each one."""
    conn = _conn_with_reasons(3)
    monkeypatch.setattr(
        llm,
        "_call_structured_strict",
        lambda *a, **k: (_ for _ in ()).throw(llm.LLMUnavailable(stage, "detail")),
    )

    with pytest.raises(llm.LLMUnavailable) as excinfo:
        llm.analyze_preferences(conn)

    assert excinfo.value.stage == stage
    assert excinfo.value.evidence == 3


def test_call_structured_lenient_wrapper_still_returns_none(monkeypatch, capsys):
    """The four per-listing callers skip on failure. That behavior is unchanged."""
    monkeypatch.setattr(
        llm,
        "_call_structured_strict",
        lambda *a, **k: (_ for _ in ()).throw(llm.LLMUnavailable("call", "boom")),
    )

    assert llm._call_structured("m", "sys", "prompt", llm.PrefAnalysis) is None
    assert "llm call err" in capsys.readouterr().out
