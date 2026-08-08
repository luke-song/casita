"""Rank listings by fit.

Heuristic baseline. Higher score = better.

Inputs are weighted in line with stated priorities, in priority order:
  - Dogs OK (large or any-size) — gate; no-dogs heavily penalized
  - Walk-to-Presidio (trail access) — primary
  - Walk-to-beach — secondary
  - 3 bedrooms preferred, ≥ 1.5 baths preferred
  - In-unit laundry > shared > hookups
  - Garage parking > street > none

Walking times come from the `walk_map` populated by walk.populate_for().
When None, score is computed without those terms.
"""
from dataclasses import dataclass, field

from .models import Listing


@dataclass
class Scored:
    """A score, plus what the score was allowed to look at.

    `score()` returns one integer, and one integer cannot say whether a listing
    lost a point or was never measured. A missing laundry field and an
    apartment with no laundry both contribute zero.

      considered — the policy has an opinion and the listing had the data
      unknown    — the policy has an opinion and the listing had no data
      unscored   — the listing has the data and the policy has no opinion

    `total` is the same number `score()` returns. The three lists are the part
    that was previously discarded.
    """

    total: int = 0
    considered: list[tuple[str, int]] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)
    unscored: list[str] = field(default_factory=list)
    gated_on: str | None = None

    def add(self, points: int, term: str) -> None:
        """The policy had an opinion and the listing had the data to apply it."""
        self.total += points
        self.considered.append((term, points))

    def missing(self, term: str) -> None:
        """The policy wanted to look and the listing did not say."""
        self.unknown.append(term)

    def blind(self, term: str) -> None:
        """The listing says, and the policy never asks."""
        self.unscored.append(term)


def _hood_fallback_bonus(listing: Listing) -> int:
    """Small extra credit for target SF neighborhoods."""
    hood = (listing.hood or "").lower()
    if any(h in hood for h in ["inner richmond", "lake street", "presidio heights"]):
        return 6
    if "inner sunset" in hood:
        return 5
    if "presidio" in hood:
        return 4
    if any(h in hood for h in ["central richmond", "central sunset", "outer richmond"]):
        return 2
    if "outer sunset" in hood or "parkside" in hood:
        return 1
    return 0


def _walk_bonus(minutes: int | None, *, sweet_spot: int) -> int:
    """Sigmoid-ish: a 5-min walk should clearly beat 20-min, but 20 vs 25 is noise."""
    if minutes is None:
        return 0
    if minutes <= sweet_spot:
        return 15
    if minutes <= sweet_spot + 5:
        return 10
    if minutes <= sweet_spot + 10:
        return 5
    if minutes <= sweet_spot + 20:
        return 1
    return -3


def score(listing: Listing, walk_map: dict | None = None) -> int:
    s = 0

    # Dog policy — gate.
    if listing.dog_policy == "no_dogs" or listing.pets_allowed is False:
        return -1000
    if listing.dog_policy == "small_only":
        s -= 30  # not a hard gate, but large dogs need negotiation.
    if listing.dog_policy == "large_ok":
        s += 12
    elif listing.dog_policy == "dogs_ok":
        s += 6

    # Walk times — Presidio is primary.
    if walk_map is not None:
        # Use minimum of presidio gates / beaches as the listing's value.
        from .walk import BEACHES, PRESIDIO_GATES, nearest
        np = nearest(walk_map, listing.key, PRESIDIO_GATES)
        nb = nearest(walk_map, listing.key, BEACHES)
        if np:
            s += _walk_bonus(np[1], sweet_spot=10) * 2  # weighted ×2 — stated priority
        if nb:
            s += _walk_bonus(nb[1], sweet_spot=10)

    s += _hood_fallback_bonus(listing)

    # Size / config.
    if listing.beds and listing.beds >= 3:
        s += 4
    if listing.baths and listing.baths >= 1.5:
        s += 5

    # Laundry.
    if listing.laundry == "in-unit":
        s += 3
    elif listing.laundry == "shared (in building)":
        s += 1
    elif listing.laundry in ("hookups only", "none"):
        s -= 2

    # Parking.
    if listing.parking and "no parking" not in (listing.parking or "").lower() and listing.parking != "none":
        s += 2
    if listing.parking and ("garage" in listing.parking.lower()):
        s += 2

    return s


# What each term can contribute, as the policy is written. This is a claim
# about score(), so tests/test_term_weights.py probes score() with synthetic
# listings and confirms every bound rather than trusting the table — a
# hand-written weight table is exactly the kind of documentation that drifts
# and then reports something nobody checked.
TERM_WEIGHTS: dict[str, tuple[int, int]] = {
    "dog policy": (-1000, 12),
    "walk to Presidio": (-6, 30),
    "walk to beach": (-3, 15),
    "neighborhood": (0, 6),
    "bathrooms": (0, 5),
    "bedrooms": (0, 4),
    "parking": (0, 4),
    "laundry": (-2, 3),
}

GATE_TERMS = frozenset({"dog policy"})


def terms_by_weight() -> list[tuple[str, int, int]]:
    """(term, low, high), heaviest first, measured by how far the term can move a score.

    The order is the answer to a question the score cannot answer on its own:
    what is this policy mostly about?
    """
    return sorted(
        ((term, lo, hi) for term, (lo, hi) in TERM_WEIGHTS.items()),
        key=lambda t: t[2] - t[1],
        reverse=True,
    )


def score_detail(listing: Listing, walk_map: dict | None = None) -> Scored:
    """`score()`, with the reasoning kept instead of thrown away.

    This mirrors `score()` term for term and returns the same total. It is a
    deliberate duplication: `score()` is the shipped policy and stays the
    reference, and `test_score_detail_totals_match_score` holds the two
    together across the whole fixture.
    """
    s = Scored()

    # Terms the listing carries and the policy never reads. Rent is the one
    # worth staring at: it is on every listing, and two apartments $7,000 apart
    # can tie.
    if listing.price is not None:
        s.blind("rent")
    if listing.sqft is not None:
        s.blind("square footage")
    if listing.has_yard is not None:
        s.blind("yard")

    # Dog policy — gate.
    if listing.dog_policy == "no_dogs" or listing.pets_allowed is False:
        s.add(-1000, "dog policy")
        s.gated_on = "dog policy"
        # Everything below this line is why a gated listing is the least
        # examined score on the page, not the most thoroughly rejected one.
        return s
    if listing.dog_policy is None and listing.pets_allowed is None:
        s.missing("dog policy")
    elif listing.dog_policy == "small_only":
        s.add(-30, "dog policy")  # not a hard gate, but large dogs need negotiation
    elif listing.dog_policy == "large_ok":
        s.add(12, "dog policy")
    elif listing.dog_policy == "dogs_ok":
        s.add(6, "dog policy")
    else:
        s.add(0, "dog policy")

    # Walk times — Presidio is primary.
    if walk_map is None:
        # No route matrix at all. The two highest-weighted terms in the policy
        # are simply absent, and the total that comes out looks like a
        # low-walkability listing rather than an unmeasured one.
        s.missing("walk to Presidio")
        s.missing("walk to beach")
    else:
        from .walk import BEACHES, PRESIDIO_GATES, nearest
        np = nearest(walk_map, listing.key, PRESIDIO_GATES)
        nb = nearest(walk_map, listing.key, BEACHES)
        if np:
            s.add(_walk_bonus(np[1], sweet_spot=10) * 2, "walk to Presidio")
        else:
            s.missing("walk to Presidio")
        if nb:
            s.add(_walk_bonus(nb[1], sweet_spot=10), "walk to beach")
        else:
            s.missing("walk to beach")

    if listing.hood:
        s.add(_hood_fallback_bonus(listing), "neighborhood")
    else:
        s.missing("neighborhood")

    # Size / config.
    if listing.beds is None:
        s.missing("bedrooms")
    else:
        s.add(4 if listing.beds >= 3 else 0, "bedrooms")
    if listing.baths is None:
        s.missing("bathrooms")
    else:
        s.add(5 if listing.baths >= 1.5 else 0, "bathrooms")

    # Laundry.
    if listing.laundry is None:
        s.missing("laundry")
    elif listing.laundry == "in-unit":
        s.add(3, "laundry")
    elif listing.laundry == "shared (in building)":
        s.add(1, "laundry")
    elif listing.laundry in ("hookups only", "none"):
        s.add(-2, "laundry")
    else:
        s.add(0, "laundry")

    # Parking.
    if listing.parking is None:
        s.missing("parking")
    else:
        p = listing.parking.lower()
        points = 0
        if listing.parking and "no parking" not in p and listing.parking != "none":
            points += 2
        if listing.parking and "garage" in p:
            points += 2
        s.add(points, "parking")

    return s


ELIMINATED_STATUSES = frozenset({"declined_by_landlord", "declined_by_us", "passed_on"})

# Active CRM pipeline — the listings we're actually pursuing. Higher strength =
# further along; orders within the pipeline bucket after vote weight.
PIPELINE_STRENGTH = {
    "applied": 5,
    "viewing_done": 4,
    "viewing_scheduled": 3,
    "shortlist": 2,
    "contacted": 1,
}


def rank(
    listings: list[Listing],
    walk_map: dict | None = None,
    status_map: dict[str, str] | None = None,
    vote_scores: dict[str, int] | None = None,
) -> list[Listing]:
    """Sort order — six buckets:
     -2. Active pipeline — a live CRM status (contacted → viewing → applied):
         the real to-do list, above everything. Within: more up-voters first,
         then further-along status, then llm_rank.
     -1. Favorites — net-upvoted (and not in pipeline/eliminated). An explicit
         human "yes" beats the ranker. Within: more up-voters first, then rank.
      0. Ranked + not filtered (severity ok / concerns), by llm_rank ascending
      1. New listings without an llm_rank yet (don't punish for being unranked)
      2. Filtered listings (severity=filtered)
      3. Eliminated — landlord-declined / we-passed / out-of-area, at the bottom

    Eliminated is soft-delete: we keep them visible at the end so we don't lose
    track of past leads. An eliminated listing stays down even if it was once
    up-voted or in the pipeline — the explicit pass is the newer, stronger
    signal. Within each bucket, ties break on heuristic score.
    """
    status_map = status_map or {}
    vote_scores = vote_scores or {}
    def sort_key(L: Listing) -> tuple:
        net = vote_scores.get(L.key, 0)
        status = status_map.get(L.key)
        strength = PIPELINE_STRENGTH.get(status, 0)
        if status in ELIMINATED_STATUSES:
            bucket = 3
        elif strength:
            bucket = -2
        elif net > 0:
            bucket = -1
        elif L.llm_severity == "filtered" or (L.llm_rank or 0) >= 9000:
            bucket = 2
        elif L.llm_rank is None:
            bucket = 1
        else:
            bucket = 0
        return (bucket, -net, -strength, L.llm_rank or 0, -score(L, walk_map))
    return sorted(listings, key=sort_key)
