"""What a source run actually covered.

A blocked search and an empty search both used to return `[]`. `search` reads
that list twice: once to upsert what it found, and once — through
`succeeded_sources` — to decide which listings are gone from the market and
should be marked inactive.

That second read is where the difference costs something. `storage.upsert_run`
already refuses to delist a source that returned nothing at all, for exactly
this reason:

    a captcha-blocked source returning 0 shouldn't wipe its prior inventory

But blocking happens per search area, and that guard is per source. Zillow and
Zumper each search eight neighborhoods. If one neighborhood answers and seven
are blocked, the source looks like it succeeded, and every listing in the seven
that were never read is marked inactive — not because it left the market, but
because nobody could look.

`ScrapeOutcome` carries the coverage alongside the listings so the caller can
tell "we looked everywhere and these are gone" from "we could not look".
"""

from dataclasses import dataclass, field

from .models import Listing


class SourceUnavailable(Exception):
    """This area could not be read, so we have no listings — not zero listings.

    `stage` says how far the fetch got, which is the part a reader needs:

      "load"    — the page never loaded
      "blocked" — the page loaded and the results never appeared, which is what
                  a bot wall looks like from here
      "parse"   — the page loaded and the extractor failed on it
    """

    def __init__(self, area: str, stage: str, detail: str = ""):
        self.area = area
        self.stage = stage
        self.detail = detail
        super().__init__(f"{area}: {stage}" + (f" — {detail}" if detail else ""))


@dataclass
class ScrapeOutcome:
    """Listings from one source, plus which of its areas were actually read."""

    listings: list[Listing] = field(default_factory=list)
    covered: list[str] = field(default_factory=list)
    blocked: list[tuple[str, str]] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        """Every area answered, so "not seen this run" means "gone"."""
        return not self.blocked

    def record(self, area: str, listings: list[Listing]) -> None:
        self.covered.append(area)
        self.listings.extend(listings)

    def miss(self, area: str, stage: str) -> None:
        self.blocked.append((area, stage))

    def summary(self) -> str:
        """One line for the run log. Silence about a gap is how this got missed."""
        if self.complete:
            return f"{len(self.listings)} listings from {len(self.covered)} areas"
        total = len(self.covered) + len(self.blocked)
        gaps = ", ".join(f"{area} ({stage})" for area, stage in self.blocked)
        return (
            f"{len(self.listings)} listings from {len(self.covered)} of {total} areas — "
            f"{len(self.blocked)} unread: {gaps}"
        )


def sources_with_full_coverage(outcomes: dict[str, ScrapeOutcome]) -> list[str]:
    """Sources allowed to delist: the ones that read every area they search.

    `storage.upsert_run` treats "this source reported in and did not mention
    that listing" as "the listing is gone". That inference needs the source to
    have actually looked everywhere, so a run with any unread area does not
    grant it.
    """
    return [name for name, outcome in outcomes.items() if outcome.complete]
