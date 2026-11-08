"""The request of the stage planner: a typed model that the gates read (#4046).

One `StageRequest` holds what the model reads about an item and what the gates need to judge the
reply. `for_model` gives the JSON the model gets, with no gate-only field. `gate_arguments` gives
the arguments of `check_proposal` and `check_gates`, so a gate runs again from a kept request and a
tree, with no planner object.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.roadmap.stage.stage_overlap import Overlap

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Mapping, Sequence

    from devops_cli.roadmap.agent_run import TraceFacts
    from devops_cli.roadmap.stage.stage_paths import StagedTree
    from devops_cli.roadmap.stage.stage_registry import RegistryCount

# The fields that only the gates read. The model never gets them.
GATE_ONLY_FIELDS: Final[frozenset[str]] = frozenset(
    {"issue_body", "probe_lines", "overlap_pulls", "creators"}
)


class StageRequest(BaseModel):
    """The request for one item. The fields up to `probes` are the JSON that the model reads, in
    key order. A field that is `None` is absent from that JSON. The last four fields are the
    inputs of the gates."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    number: int
    title: str
    # The body, cut to the token limit of the request.
    body: str
    context: str
    capabilities: list[Any]
    budget: int
    rejected_plan: str | None = None
    # The open pull requests that change a cited path, as the model reads them.
    overlaps: list[dict[str, Any]] | None = None
    metric_senders: dict[str, list[str]] | None = None
    # The text of the premise probe.
    probes: str | None = None
    # The whole body of the issue: the criteria gate reads each criterion in it.
    issue_body: str = ""
    # The lines of the premise probe, for the quote rule of `feasibility` (#3200).
    probe_lines: tuple[str, ...] = ()
    # The same open pull requests as `overlaps`, as objects: the dependencies gate reads them.
    overlap_pulls: tuple[Overlap, ...] = ()
    # The paths that the plans of open items create, each with its item (#3418).
    creators: dict[str, int] = Field(default_factory=dict)

    def for_model(self) -> dict[str, Any]:
        """The JSON that the model reads: no gate-only field, and no key that is `None`."""
        sent = self.model_dump(exclude=set(GATE_ONLY_FIELDS))
        return {key: value for key, value in sent.items() if value is not None}


def gate_arguments(
    request: StageRequest,
    tree: StagedTree,
    *,
    known: Collection[str],
    requirements: Mapping[str, Collection[str]] | None = None,
    requirement_texts: Mapping[str, Mapping[str, str]] | None = None,
    search_evidence: Mapping[str, Sequence[str]] | None = None,
    read_text: Callable[[str], str | None] | None = None,
    registry: Sequence[RegistryCount] | None = None,
    constants: Mapping[str, int] | None = None,
    references: Sequence[str] = (),
    models: Mapping[str, tuple[str, Sequence[str]]] | None = None,
    manifest_references: Mapping[str, Sequence[str]] | None = None,
    trace: TraceFacts | None = None,
) -> dict[str, Any]:
    """The keyword arguments of `check_proposal` and `check_gates` after the proposal. The request
    gives the inputs that the item fixes; the other inputs depend on the commit and on the
    proposal, so the caller gives them."""
    return {
        "known": known,
        "tree": tree,
        "requirements": requirements,
        "requirement_texts": requirement_texts,
        "issue_body": request.issue_body,
        "probes": request.probe_lines,
        "overlaps": request.overlap_pulls,
        "search_evidence": search_evidence,
        "plan_creates": request.creators,
        "read_text": read_text,
        "registry": registry,
        "constants": constants,
        "references": references,
        "models": models,
        "manifest_references": manifest_references,
        "trace": trace,
    }
