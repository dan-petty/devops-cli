"""The hand-off of a review session's findings about merged code to roadmap intake (#2420).

`devops review intake` takes one session. It refuses the session when it is not on merged code
(`review.checkout`), takes the session's qualifying findings, leaves out each finding that an
issue already settles (`review.filed_findings`, #2419), and hands each other one to roadmap
intake as one candidate, through `intake_candidate`, the one entry point for new items (#742).

A finding qualifies when admission gave it a fingerprint v2 and no verdict invalidated or
mitigated it. Admission writes the fingerprint v2 of an admitted tool finding into findings.json
and saves no suppressed finding, so such a finding is OPEN. The candidate of a finding carries
the finding's marker, so the issue that intake files keeps the same finding out of a later run.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from devops_cli.ai.review_schema import ReviewSessionPayload, SavedFinding
from devops_cli.config.constants import (
    CONST_REVIEW_FINDINGS_FILENAME,
    CONST_STATUS_INVALIDATED,
    CONST_STATUS_MITIGATED,
)
from devops_cli.config.defaults import DEFAULT_REVIEW_INTAKE_TITLE_CHARS
from devops_cli.dry_run import PlannedRequest
from devops_cli.exceptions import SecurityError
from devops_cli.exceptions.ai import ReviewHandOffRefusedError
from devops_cli.lang import MESSAGES
from devops_cli.review.checkout import is_clean_path_review, why_not_on_merged_code
from devops_cli.review.filed_findings import finding_marker, read_filed_findings
from devops_cli.review.fingerprint import is_fingerprint_v2
from devops_cli.roadmap.intake import (
    CandidateOutcome,
    Filer,
    IntakePlan,
    NewCandidate,
    Outcome,
    dry_run_intake,
    intake_candidate,
    render_intake,
)
from devops_cli.roadmap.intake_model import IntakeModel
from devops_cli.roadmap.intake_requests import SpendMeter
from devops_cli.roadmap.store import RoadmapStore

# A verdict that takes a finding out of the hand-off: a person or the review found it not valid,
# or found that something already stops it.
_LEFT_OUT_VERDICTS = frozenset({CONST_STATUS_INVALIDATED, CONST_STATUS_MITIGATED})


def qualifying_findings(payload: ReviewSessionPayload) -> list[SavedFinding]:
    """The findings of the session, in their order, that go to intake: each has a fingerprint v2
    and a verdict that keeps it."""
    return [
        finding
        for finding in payload.findings
        if is_fingerprint_v2(finding.fingerprint) and finding.status not in _LEFT_OUT_VERDICTS
    ]


def _title(finding: SavedFinding) -> str:
    """`fix: <finding title> (<location>)`, on one line, cut to the longest title intake files."""
    title = " ".join(f"fix: {finding.title} ({finding.location})".split())
    return title[:DEFAULT_REVIEW_INTAKE_TITLE_CHARS]


def _sections(finding: SavedFinding) -> list[str]:
    """The cited code, the fix and the verification criteria that the finding has."""
    texts = MESSAGES.review
    sections: list[str] = []
    if finding.cited_code is not None:
        sections.append(f"{texts.hand_off_cited_code}\n\n```\n{finding.cited_code.excerpt}\n```")
    if finding.fix:
        sections.append(f"{texts.hand_off_fix}\n\n{finding.fix}")
    if finding.verification_criteria:
        criteria = "\n".join(f"- {criterion}" for criterion in finding.verification_criteria)
        sections.append(f"{texts.hand_off_criteria}\n\n{criteria}")
    return sections


def finding_candidate(finding: SavedFinding, session: str) -> NewCandidate:
    """The intake candidate of a qualifying finding of `session`: it cites the finding, and its
    body ends with the finding's marker."""
    evidence = MESSAGES.review.hand_off_body.format(
        tool=finding.producer,
        description=finding.description or finding.title,
        session=session,
        location=finding.location,
        severity=finding.severity,
        verdict=finding.status,
    )
    body = "\n\n".join([evidence, *_sections(finding), finding_marker(finding.fingerprint)])
    return NewCandidate(title=_title(finding), body=body, filed_by=Filer.AGENT)


def intake_hint(payload: ReviewSessionPayload, session: str) -> str | None:
    """The line `review path` prints when the session reviewed a clean tree and has qualifying
    findings: their count and the command. It runs no git, sends no request and calls no model;
    the command makes the full merged-code test."""
    if not is_clean_path_review(payload):
        return None
    count = len(qualifying_findings(payload))
    if not count:
        return None
    return MESSAGES.review.hand_off_hint.format(count=count, session=session)


def read_session(session_dir: Path) -> ReviewSessionPayload:
    """The findings.json of the session in `session_dir`."""
    path = session_dir / CONST_REVIEW_FINDINGS_FILENAME
    return ReviewSessionPayload.model_validate_json(path.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class HandOff:
    """What a hand-off sends to intake: the session, its qualifying findings, the candidates of
    those that no issue settles, in order, and how many an issue settles. A dry run holds every
    qualifying finding's candidate, and the requests a real run makes instead of any it made."""

    session: str
    qualifying: int
    candidates: tuple[NewCandidate, ...] = ()
    settled: int = 0
    requests: tuple[PlannedRequest, ...] = ()
    writes: tuple[PlannedRequest, ...] = ()


def _refuse_secrets(findings: list[SavedFinding], candidates: list[NewCandidate]) -> None:
    """Stop the hand-off, naming the finding, when a candidate's text looks like a secret."""
    for finding, candidate in zip(findings, candidates, strict=True):
        try:
            candidate.refuse_secrets()
        except SecurityError as exc:
            message = MESSAGES.review.hand_off_secret.format(location=finding.location)
            raise SecurityError(message) from exc


def prepare_hand_off(session_dir: Path, repository: Path, *, repo: str, dry_run: bool) -> HandOff:
    """The hand-off of the session in `session_dir` to the roadmap intake of `repo`.

    `repository` is the checkout whose `origin/main` decides whether the session is on merged
    code. A session that is not raises `ReviewHandOffRefusedError`, and a candidate that looks
    like it holds a secret raises `SecurityError`, both before any request. A real run then reads
    the issues that carry a finding marker, with one search; a dry run makes no request and
    holds the requests a real run makes, with intake's for the first candidate.
    """
    session = session_dir.name
    payload = read_session(session_dir)
    reason = why_not_on_merged_code(payload, repository)
    if reason is not None:
        refused = MESSAGES.review.hand_off_refused.format(session=session, reason=reason)
        raise ReviewHandOffRefusedError(refused, session=session)
    findings = qualifying_findings(payload)
    candidates = [finding_candidate(finding, session) for finding in findings]
    _refuse_secrets(findings, candidates)
    if not findings:
        return HandOff(session=session, qualifying=0)
    filed = read_filed_findings(repo, dry_run=dry_run)
    if dry_run:
        intake = dry_run_intake(repo, new=candidates[0])
        return HandOff(
            session=session,
            qualifying=len(findings),
            candidates=tuple(candidates),
            requests=(*filed.requests, *intake.requests),
            writes=intake.writes,
        )
    kept = filed.unfiled(
        list(zip(findings, candidates, strict=True)), fingerprint=lambda pair: pair[0].fingerprint
    )
    return HandOff(
        session=session,
        qualifying=len(findings),
        candidates=tuple(candidate for _, candidate in kept),
        settled=len(findings) - len(kept),
    )


@dataclass(frozen=True)
class HandOffReport:
    """What intake did with each candidate: its outcome, intake's report of every decision with
    what the run spent, the issues it filed, and how many candidates it skipped."""

    outcomes: tuple[CandidateOutcome, ...]
    text: str

    @property
    def filed(self) -> tuple[int, ...]:
        return tuple(outcome.number for outcome in self.outcomes if outcome.number is not None)

    @property
    def skipped(self) -> int:
        return sum(outcome.decision.outcome is Outcome.SKIP for outcome in self.outcomes)

    def render(self, *, confirm: bool) -> str:
        """Intake's report, then what the run wrote: each issue filed and each candidate
        skipped with `confirm`, or that a plan wrote nothing."""
        texts = MESSAGES.review
        lines = [self.text.rstrip()]
        if not confirm:
            lines.append(texts.hand_off_plan_note)
        lines += [texts.hand_off_filed.format(number=number) for number in self.filed]
        if confirm and self.skipped:
            lines.append(texts.hand_off_skipped.format(count=self.skipped))
        return "\n".join(lines) + "\n"


def run_hand_off(
    hand_off: HandOff,
    *,
    repo: str,
    store: RoadmapStore,
    model: IntakeModel,
    confirm: bool,
    meter: SpendMeter | None = None,
) -> HandOffReport:
    """Hand each candidate to roadmap intake in turn, through one store and one model; with
    `confirm`, intake files and places it. `meter` counts what the run spends, from when the
    caller made it; a new one counts from here. A write that fails stops the run: each issue
    filed before it carries its finding's marker, so the next run leaves that finding out."""
    meter = meter or SpendMeter()
    metered = meter.model(model)
    outcomes = tuple(
        intake_candidate(store, candidate, repo=repo, model=metered, confirm=confirm)
        for candidate in hand_off.candidates
    )
    plan = IntakePlan(decisions=tuple(o.decision for o in outcomes), spend=meter.spend())
    return HandOffReport(outcomes=outcomes, text=render_intake(plan, repo=repo))


__all__ = [
    "HandOff",
    "HandOffReport",
    "finding_candidate",
    "intake_hint",
    "prepare_hand_off",
    "qualifying_findings",
    "read_session",
    "run_hand_off",
]
