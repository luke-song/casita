"""A score of zero has two causes, and the integer cannot tell them apart.

`score_detail` mirrors `score` term for term. The mirroring is the risk in this
change, so the first test here is the one that holds the two together across
the whole fixture.
"""

import shutil

import casita
from casita import storage, walk
from casita.models import Listing
from casita.rank import score, score_detail


def _listing(**kw) -> Listing:
    base = dict(source="zillow", source_id="1", url="https://example.com/1")
    return Listing(**(base | kw))


def test_score_detail_totals_match_score_across_the_fixture(tmp_path, monkeypatch):
    """286 comparisons: every fixture listing, with and without the route matrix."""
    db_path = tmp_path / "demo.sqlite"
    shutil.copy2(casita.DEMO_FIXTURE, db_path)
    monkeypatch.setenv("CASITA_DB_PATH", str(db_path))
    monkeypatch.setenv("CASITA_ROUTE_CACHE_DB", str(db_path))
    monkeypatch.setenv("CASITA_ROUTES_OFFLINE", "1")

    with storage.connect() as conn:
        listings = storage.active_listings(conn)
    walk_map = walk.populate_for(listings)

    assert len(listings) > 100
    for walk_arg in (None, walk_map):
        for L in listings:
            assert score_detail(L, walk_arg).total == score(L, walk_arg), L.key


def test_score_detail_absent_parking_and_no_parking_differ_at_equal_totals():
    """The whole point, in one assertion.

    A listing that never mentioned parking and a listing with no parking both
    contribute zero. The integer cannot separate them; the lists can.
    """
    silent = score_detail(_listing(parking=None))
    stated = score_detail(_listing(parking="none"))

    assert silent.total == stated.total
    assert "parking" in silent.unknown
    assert ("parking", 0) in stated.considered
    assert "parking" not in stated.unknown


def test_score_detail_no_route_matrix_reports_walk_terms_as_unmeasured():
    """Without routes the two highest-weighted terms vanish, and say so."""
    d = score_detail(_listing(dog_policy="large_ok"), walk_map=None)

    assert "walk to Presidio" in d.unknown
    assert "walk to beach" in d.unknown


def test_score_detail_gated_listing_reports_the_gate_and_stops():
    """A gate is the least examined score on the page, not the most rejected."""
    d = score_detail(_listing(dog_policy="no_dogs", beds=3, baths=2, laundry="in-unit"))

    assert d.total == -1000
    assert d.gated_on == "dog policy"
    assert d.considered == [("dog policy", -1000)]
    # Beds, baths and laundry were on the listing and never looked at.
    assert d.unknown == []


def test_score_detail_rent_is_reported_as_outside_the_policy():
    """Rent is on every listing and is not a term, so two prices can tie."""
    cheap = score_detail(_listing(price=1800, dog_policy="dogs_ok"))
    dear = score_detail(_listing(price=9000, dog_policy="dogs_ok"))

    assert cheap.total == dear.total
    assert "rent" in cheap.unscored
    assert "rent" in dear.unscored
