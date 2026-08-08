"""A weight table is a claim about the scorer, so it gets checked like one.

`TERM_WEIGHTS` is what `casita why` prints when it says what the policy weighs
most. Hand-written tables drift from the code they describe and then report
something nobody verified — which is the failure this whole branch is about.
These tests probe `score()` with synthetic listings and confirm every bound.
"""

import pytest

from casita import walk
from casita.models import Listing
from casita.rank import TERM_WEIGHTS, score, score_detail, terms_by_weight


def _listing(**kw) -> Listing:
    base = dict(source="zillow", source_id="1", url="https://example.com/1")
    return Listing(**(base | kw))


# A listing that clears the gate and carries no other scored fact. Every
# probe below is measured as a delta from this.
def _baseline() -> Listing:
    return _listing(dog_policy="dogs_ok")


BASE_TERM_POINTS = 6  # dogs_ok, confirmed by test_dog_policy_bounds_match_score


def _walk_map(presidio_minutes: int, beach_minutes: int) -> dict:
    m = {}
    for a in walk.PRESIDIO_GATES:
        m[("zillow:1", a.name)] = presidio_minutes
    for a in walk.BEACHES:
        m[("zillow:1", a.name)] = beach_minutes
    return m


def test_dog_policy_bounds_match_score():
    lo, hi = TERM_WEIGHTS["dog policy"]

    assert score(_listing(dog_policy="no_dogs")) == lo
    assert score(_listing(dog_policy="large_ok")) == hi
    assert score(_baseline()) == BASE_TERM_POINTS


@pytest.mark.parametrize(
    "term,near,far",
    [("walk to Presidio", 5, 40), ("walk to beach", 5, 40)],
)
def test_walk_bounds_match_score(term, near, far):
    """Both walk terms peak on a short walk and bottom out past the last band."""
    base = score(_baseline())
    lo, hi = TERM_WEIGHTS[term]
    other = "walk to beach" if term == "walk to Presidio" else "walk to Presidio"
    other_lo, other_hi = TERM_WEIGHTS[other]

    if term == "walk to Presidio":
        best = _walk_map(near, far)
        worst = _walk_map(far, far)
    else:
        best = _walk_map(far, near)
        worst = _walk_map(far, far)

    # The other term sits at its floor in both probes, so it cancels out.
    assert score(_baseline(), best) - base == hi + other_lo
    assert score(_baseline(), worst) - base == lo + other_lo


@pytest.mark.parametrize(
    "term,high_kw,low_kw",
    [
        ("neighborhood", {"neighborhood": "Inner Richmond"}, {}),
        ("bathrooms", {"baths": 2}, {"baths": 1}),
        ("bedrooms", {"beds": 3}, {"beds": 1}),
        ("parking", {"parking": "garage"}, {"parking": "none"}),
        ("laundry", {"laundry": "in-unit"}, {"laundry": "none"}),
    ],
)
def test_flat_term_bounds_match_score(term, high_kw, low_kw):
    base = score(_baseline())
    lo, hi = TERM_WEIGHTS[term]

    assert score(_listing(dog_policy="dogs_ok", **high_kw)) - base == hi
    assert score(_listing(dog_policy="dogs_ok", **low_kw)) - base == lo


def test_terms_by_weight_orders_by_how_far_a_term_can_move_a_score():
    order = [t for t, _, _ in terms_by_weight()]

    assert order[0] == "dog policy", "the gate dominates everything"
    assert order[1:3] == ["walk to Presidio", "walk to beach"], (
        "the claim casita why prints — that this is mostly a walkability "
        "score — depends on these two ranking directly under the gate"
    )


def test_every_scored_term_has_a_declared_weight():
    """A term the score uses but the table omits would print as if it were absent."""
    rich = _listing(
        dog_policy="dogs_ok", neighborhood="Inner Richmond",
        beds=3, baths=2, laundry="in-unit", parking="garage",
    )
    scored = score_detail(rich, _walk_map(5, 5))

    for term, _points in scored.considered:
        assert term in TERM_WEIGHTS, term
