"""A source that could not look has not established that anything is gone.

`storage.upsert_run` marks a listing inactive when a source reported in and the
listing was not among what it reported. That inference is only sound if the
source actually read everywhere it searches. Blocking happens per area; the
guard was per source, so one readable area was enough to delist every listing
in the areas nobody could open.
"""

import pytest

from casita import storage
from casita.models import Listing
from casita.sources import (
    ScrapeOutcome,
    SourceUnavailable,
    sources_with_full_coverage,
)


def _listing(area: str, i: int) -> Listing:
    return Listing(
        source="redfin",
        source_id=f"{area}-{i}",
        url=f"https://example.com/{area}/{i}",
        title=f"{area} #{i}",
        neighborhood=area,
        price=3000,
    )


AREAS = ("area-a", "area-b", "area-c")
FULL_RUN = [_listing(a, i) for a in AREAS for i in (1, 2, 3)]
ONE_AREA_ONLY = [_listing("area-a", i) for i in (1, 2, 3)]


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("CASITA_DB_PATH", str(tmp_path / "t.sqlite"))
    with storage.connect() as conn:
        storage.upsert_run(conn, FULL_RUN, succeeded_sources=["redfin"])
    return None


def _active(conn) -> int:
    return conn.execute("SELECT COUNT(*) FROM listings WHERE active = 1").fetchone()[0]


def test_full_coverage_delists_listings_the_source_stopped_reporting(db):
    """The inference is sound when every area was read: not seen means gone."""
    with storage.connect() as conn:
        storage.upsert_run(conn, ONE_AREA_ONLY, succeeded_sources=["redfin"])

        assert _active(conn) == 3


def test_partial_coverage_does_not_delist_the_areas_nobody_read(db):
    """Two of three areas blocked. The six listings in them are not gone.

    This is the regression. Before, a blocked area returned [], the source
    looked like it had reported in, and these six were marked inactive — not
    because they left the market, but because nobody could look.
    """
    with storage.connect() as conn:
        storage.upsert_run(conn, ONE_AREA_ONLY, succeeded_sources=[])

        assert _active(conn) == 9


def test_scrape_outcome_with_a_blocked_area_is_not_complete():
    outcome = ScrapeOutcome()
    outcome.record("area-a", ONE_AREA_ONLY)
    outcome.miss("area-b", "blocked")

    assert outcome.complete is False
    assert outcome.listings == ONE_AREA_ONLY


def test_scrape_outcome_with_every_area_read_is_complete():
    outcome = ScrapeOutcome()
    for area in AREAS:
        outcome.record(area, [])

    assert outcome.complete is True


def test_scrape_outcome_summary_names_the_areas_that_went_unread():
    """Silence about a gap is how this went unnoticed, so the gap gets a line."""
    outcome = ScrapeOutcome()
    outcome.record("area-a", ONE_AREA_ONLY)
    outcome.miss("area-b", "blocked")
    outcome.miss("area-c", "load")
    summary = outcome.summary()

    assert "1 of 3 areas" in summary
    assert "area-b (blocked)" in summary
    assert "area-c (load)" in summary


def test_scrape_outcome_summary_stays_quiet_when_nothing_was_missed():
    outcome = ScrapeOutcome()
    outcome.record("area-a", ONE_AREA_ONLY)

    assert outcome.summary() == "3 listings from 1 areas"


def test_source_unavailable_carries_the_area_and_the_stage():
    e = SourceUnavailable("outer-sunset", "blocked", "timeout")

    assert e.area == "outer-sunset"
    assert e.stage == "blocked"
    assert "outer-sunset" in str(e)


def test_only_fully_covered_sources_may_delist():
    """The wiring: coverage decides who gets to say a listing is gone."""
    read_everything = ScrapeOutcome()
    read_everything.record("area-a", [])

    hit_a_wall = ScrapeOutcome()
    hit_a_wall.record("area-a", ONE_AREA_ONLY)
    hit_a_wall.miss("area-b", "blocked")

    granted = sources_with_full_coverage(
        {"zillow": read_everything, "redfin": hit_a_wall}
    )

    assert granted == ["zillow"]
    # redfin still contributed listings; it just cannot claim anything is gone.
    assert hit_a_wall.listings == ONE_AREA_ONLY
