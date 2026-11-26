"""The decision point `brain.reference_relevance` (ADR 0020, ADR 0023 section 7, #4672).

The reference step picks its links with the gates and the rank, which is the fallback of the
point. The point asks the decision model one closed question about each link that the fallback
picks: is the candidate file off the need of the item? A probability under the `continue_below`
cut gives the band *continue*, which links the candidate. *review* leaves it out, and *flag* leaves
it out and logs it.

The point runs in `shadow` only: the chain writes the decision record and the count, and the step
changes no link and no rank for a band. Its cuts file holds start cuts with no labelled case, and
the fit bar refuses the mode `on` until a fit. The digest holds text of a public repository, so the
step does not run the point for a private repository (ADR 0023 section 7).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from pydantic_ai.models.decision import NoulQuestion

from devops_cli.config.constants import CONST_ROADMAP_ALTERNATIVES_REFERENCE_RELEVANCE_SECONDS
from devops_cli.roadmap.decision_point import DecisionPoint, ResolverChain, chain_of
from devops_cli.roadmap.decision_step import Band

if TYPE_CHECKING:
    from pydantic_ai.models.decision import DecisionModel

    from devops_cli.config.settings import Settings

CUTS_FILE: Final[Path] = Path(__file__).with_name("reference_relevance_cuts.json")
# The one question of the point. A yes leaves the candidate out, as the cuts read a probability.
QUESTION: Final[str] = "off_need"
_INSTRUCTIONS: Final[str] = (
    "Is the candidate file off the need of the item: does it implement something else than what "
    "the item needs?"
)
# The size limit of each piece of the digest, in characters.
_PIECE_CHARS: Final[int] = 256


@dataclass(frozen=True)
class RelevanceCase:
    """The input of the point for one candidate: the need line of the item, the path, the
    description and the license of the candidate, and the symbols that the search matched."""

    need: str
    path: str
    description: str
    license: str
    symbols: str


def _evidence(case: RelevanceCase) -> dict[str, Any]:
    """The digest of `case`, each piece cut to the size limit."""
    pieces = {
        "need": case.need,
        "path": case.path,
        "description": case.description,
        "license": case.license,
        "matched_symbols": case.symbols,
    }
    return {name: text[:_PIECE_CHARS] for name, text in pieces.items()}


REFERENCE_RELEVANCE: Final[DecisionPoint[RelevanceCase]] = DecisionPoint(
    name="brain.reference_relevance",
    questions={QUESTION: NoulQuestion(instructions=_INSTRUCTIONS)},
    evidence=_evidence,
    bands={
        Band.CONTINUE: "Link the candidate.",
        Band.REVIEW: "Leave the candidate out.",
        Band.FLAG: "Leave the candidate out, and log it.",
    },
    cuts=CUTS_FILE,
    timeout=CONST_ROADMAP_ALTERNATIVES_REFERENCE_RELEVANCE_SECONDS,
    requires_fit_bar=True,
)


def relevance_of(
    settings: Settings, *, model: DecisionModel[Any] | None = None
) -> ResolverChain[RelevanceCase] | None:
    """The resolver chain of the point under `settings`, or None when the point does not run."""
    return chain_of(REFERENCE_RELEVANCE, settings, model=model)


__all__ = ["CUTS_FILE", "QUESTION", "REFERENCE_RELEVANCE", "RelevanceCase", "relevance_of"]
