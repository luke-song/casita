"""The output is the feature, so the output gets tested.

`score_detail` returning correct lists is not the change — a person reading a
screen and coming away with the right belief is. These tests pin the sentences
that carry that, because a refactor that silently drops "never evaluated" turns
the tool back into the thing it was.
"""

import shutil

from click.testing import CliRunner

import casita
from casita.models import Listing


def _listing(**kw) -> Listing:
    base = dict(source="zillow", source_id="1", url="https://example.com/1")
    return Listing(**(base | kw))


def _demo_env(tmp_path, monkeypatch):
    db_path = tmp_path / "demo.sqlite"
    shutil.copy2(casita.DEMO_FIXTURE, db_path)
    monkeypatch.setenv("CASITA_DB_PATH", str(db_path))
    monkeypatch.setenv("CASITA_ROUTE_CACHE_DB", str(db_path))
    monkeypatch.setenv("CASITA_ROUTES_OFFLINE", "1")


def test_why_summary_reports_measured_and_unmeasured_term_counts(tmp_path, monkeypatch):
    _demo_env(tmp_path, monkeypatch)

    result = CliRunner().invoke(casita.cli, ["why", "--local", "--no-walk"])

    assert result.exit_code == 0, result.output
    assert "scoring terms informed" in result.output
    assert "unmeasured" in result.output
    assert "most common gaps" in result.output


def test_why_summary_names_the_heaviest_terms_before_any_listing(tmp_path, monkeypatch):
    """A reader has to be able to see what the policy is about, not infer it."""
    _demo_env(tmp_path, monkeypatch)

    result = CliRunner().invoke(casita.cli, ["why", "--local", "--no-walk"])
    out = result.output

    assert "what this policy weighs most" in out
    # The weights block precedes the coverage block: policy first, then how
    # much of it we could measure.
    assert out.index("what this policy weighs most") < out.index("active listings")
    assert "walkability score" in out


def test_why_no_walk_reports_the_route_terms_as_unmeasured(tmp_path, monkeypatch):
    """Without routes the two heaviest terms vanish, and the page says so."""
    _demo_env(tmp_path, monkeypatch)

    result = CliRunner().invoke(casita.cli, ["why", "--local", "--no-walk"])

    assert "walk to Presidio" in result.output


def test_why_unknown_listing_exits_nonzero(tmp_path, monkeypatch):
    _demo_env(tmp_path, monkeypatch)

    result = CliRunner().invoke(casita.cli, ["why", "--local", "--listing", "no-such-listing"])

    assert result.exit_code != 0
    assert "no listing matches" in result.output


def test_print_listing_why_separates_measured_from_never_asked(capsys):
    """considered / unknown / unscored each get their own heading."""
    L = _listing(price=3200, dog_policy="dogs_ok", beds=2)
    casita._print_listing_why(L, casita.score_detail(L, None))
    out = capsys.readouterr().out

    assert "measured" in out
    assert "wanted to look, listing did not say" in out   # unknown
    assert "not a term in this policy" in out             # unscored
    assert "rent" in out


def test_print_listing_why_gated_listing_says_nothing_else_was_evaluated(capsys):
    """The line that stops a gated listing reading as thoroughly rejected."""
    L = _listing(price=4500, dog_policy="no_dogs", beds=3, baths=2, laundry="in-unit")
    casita._print_listing_why(L, casita.score_detail(L, None))
    out = capsys.readouterr().out

    assert "gated on dog policy" in out
    assert "never evaluated" in out
    # Beds, baths and laundry were on the listing and must not appear as
    # measured terms — the gate returned before any of them were read.
    assert "bedrooms" not in out


def test_coverage_summary_closes_with_the_sentence_that_prevents_the_misreading(capsys):
    """A thin score is a less examined listing, not a worse one."""
    casita._print_coverage_summary([_listing(dog_policy="dogs_ok", price=3000)], None)
    out = capsys.readouterr().out

    assert "less examined one" in out
