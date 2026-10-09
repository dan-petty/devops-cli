"""Verdicts a person gives through `devops review verify` (#949, #1150).

A verdict is a label on the session's files and nothing else: no catalog learns from it and no
ledger records it. A known false positive is a reviewed `.devops/review.toml` suppression.

A verdict names its finding by the number `devops review findings` shows: the finding's place in
findings.json or, for a candidate, in candidates.json, whatever status filter the listing applied.
candidates.json holds every finding the review raised and findings.json the ones it reported. A
candidate given a VERIFIED or MITIGATED verdict moves into findings.json, where reports and review
history read it. A verdict on a finding in findings.json is recorded on the candidate it reports
too, and a verdict on a candidate on its copy, so the two files agree. A candidate whose defect
findings.json already reports under another title, because consolidation merged it or kept
another persona's report of it, is judged through that finding instead.

A verdict holds the session's lock from reading its files to writing them, and when one file
cannot be written the files it already wrote are put back.
"""

from __future__ import annotations

import fcntl
import logging
from collections import defaultdict
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from devops_cli.ai.review.verdicts import apply_verdict
from devops_cli.ai.review_schema import (
    ReviewSessionPayload,
    SavedFinding,
    _are_findings_duplicate,
)
from devops_cli.config.constants import (
    CONST_REVIEW_VERDICT_LOCK_FILENAME,
    CONST_STATUS_MITIGATED,
    CONST_STATUS_UNVERIFIED,
    CONST_STATUS_VERIFIED,
    CONST_VERIFIED_BY_HUMAN,
)
from devops_cli.exceptions.validation import ValidationError
from devops_cli.lang import MESSAGES
from devops_cli.output import write_bytes_file, write_json_file

logger = logging.getLogger(__name__)

# A candidate given one of these verdicts belongs in the report.
_REPORTED_VERDICTS = frozenset({CONST_STATUS_VERIFIED, CONST_STATUS_MITIGATED})

# What a verdict writes on a finding; a candidate's copy in findings.json takes all of it.
_VERDICT_FIELDS = frozenset(
    {
        "status",
        "verified",
        "reportable",
        "mitigated",
        "verified_by",
        "verified_at",
        "invalidation_reason",
        "citation_line",
        "mitigating_mechanism",
        "verification_note",
    }
)


@dataclass(frozen=True, slots=True)
class Verdict:
    """A person's verdict to record: its status, and why."""

    status: str
    reason: str = ""


@contextmanager
def adjudicating(session_dir: Path) -> Iterator[None]:
    """Hold the session's verdict lock while a verdict reads, judges and writes its files.

    Verdicts given on one session at once take turns instead of writing over each other.
    """
    with (session_dir / CONST_REVIEW_VERDICT_LOCK_FILENAME).open("a", encoding="utf-8") as lock:
        # Closing the lock file releases the lock.
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def write_session_files(files: Sequence[tuple[Path, ReviewSessionPayload]]) -> None:
    """Write the session files a verdict changed; when one fails, put back those it wrote."""
    written: list[tuple[Path, bytes]] = []
    try:
        for path, payload in files:
            original = path.read_bytes()
            write_json_file(path, payload)
            written.append((path, original))
    except Exception:
        for path, original in reversed(written):
            try:
                write_bytes_file(path, original)
            except OSError as exc:
                logger.warning("Could not put back %s: %s", path, exc)
        raise


def numbered_finding(
    findings: Sequence[SavedFinding], number: int, field: str = "index"
) -> SavedFinding:
    """The finding `devops review findings` lists as `number`, counting from 1."""
    if not 1 <= number <= len(findings):
        raise ValidationError(
            MESSAGES.review.index_out_of_bounds.format(max_index=len(findings)), field=field
        )
    return findings[number - 1]


def number_by_title(findings: Sequence[SavedFinding], pattern: str) -> int:
    """The number of the one finding whose title contains `pattern`, ignoring case.

    A pattern that several titles contain is refused: taking the first match put verdicts on
    findings nobody had read.
    """
    needle = pattern.lower()
    matches = [n for n, f in enumerate(findings, 1) if needle in f.title.lower()]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise ValidationError(
            MESSAGES.review.title_matches_none.format(pattern=pattern), field="title"
        )
    raise ValidationError(
        MESSAGES.review.title_matches_several.format(
            pattern=pattern, numbers=", ".join(f"#{n}" for n in matches)
        ),
        field="title",
    )


def judge_reported(
    reported: ReviewSessionPayload,
    candidates: ReviewSessionPayload | None,
    number: int,
    verdict: Verdict,
) -> None:
    """Record `verdict` on finding `number` of findings.json and on each candidate it reports."""
    finding = numbered_finding(reported.findings, number)
    pool = candidates.findings if candidates is not None else []
    mirrors = _CandidateIndex(pool).candidates_of(finding)
    _record_verdict(finding, verdict)
    for n in mirrors:
        pool[n - 1] = _mirrored(pool[n - 1], finding)


def judge_candidate(
    candidates: ReviewSessionPayload,
    reported: ReviewSessionPayload,
    number: int,
    verdict: Verdict,
) -> bool:
    """Record `verdict` on candidate `number`, keeping findings.json in step; True if it moved.

    The candidate's copy in findings.json takes the verdict too. Without a copy, a VERIFIED or
    MITIGATED verdict adds one, unless findings.json reports the candidate's defect under another
    title.
    """
    candidate = numbered_finding(candidates.findings, number, field="candidate")
    copy_at = _CandidateIndex(candidates.findings).copy_of(number, reported.findings)
    if copy_at is None and verdict.status in _REPORTED_VERDICTS:
        _refuse_reported_elsewhere(reported.findings, candidate, number)
    _record_verdict(candidate, verdict)
    if copy_at is not None:
        reported.findings[copy_at] = _mirrored(reported.findings[copy_at], candidate)
        return False
    if candidate.status not in _REPORTED_VERDICTS:
        return False
    reported.findings.append(
        candidate.model_copy(update={"moved_from_candidate": number}, deep=True)
    )
    return True


def _record_verdict(finding: SavedFinding, verdict: Verdict) -> None:
    """Apply a person's `verdict` to `finding`; a reset to UNVERIFIED names no adjudicator."""
    mitigated = verdict.status == CONST_STATUS_MITIGATED
    reason = _verdict_reason(finding, verdict.status, verdict.reason)
    apply_verdict(
        finding,
        verdict.status,
        by=None if verdict.status == CONST_STATUS_UNVERIFIED else CONST_VERIFIED_BY_HUMAN,
        reason=reason,
        mitigating_mechanism=reason if mitigated else None,
    )


def _refuse_reported_elsewhere(
    reported: Sequence[SavedFinding], candidate: SavedFinding, number: int
) -> None:
    """Refuse to add a candidate whose defect findings.json reports under another title.

    The consolidator's own test decides, whatever either verdict: a second copy would count the
    defect twice in the report, in review history and in the exported dataset.
    """
    for reported_number, finding in enumerate(reported, 1):
        if _are_findings_duplicate(
            finding, candidate.model_copy(update={"status": finding.status})
        ):
            raise ValidationError(
                MESSAGES.review.candidate_already_reported.format(
                    index=number, number=reported_number
                ),
                field="candidate",
            )


def _identity(finding: SavedFinding) -> tuple[str, str, str]:
    """The persona, location and title a candidate's copy in findings.json keeps.

    Consolidation keeps the location and title of the first report it merges, and lists the
    personas of the others after that report's own.
    """
    persona = finding.persona.split(",")[0].strip().lower()
    return persona, finding.location.strip().lower(), finding.title.strip().lower()


class _CandidateIndex:
    """Which candidates in candidates.json each finding in findings.json reports."""

    def __init__(self, candidates: Sequence[SavedFinding]) -> None:
        self._candidates = candidates
        self._by_identity: defaultdict[tuple[str, str, str], list[int]] = defaultdict(list)
        for number, candidate in enumerate(candidates, 1):
            self._by_identity[_identity(candidate)].append(number)

    def candidates_of(self, finding: SavedFinding) -> list[int]:
        """The numbers of the candidates `finding` reports.

        A copy a verdict moved names its candidate. A finding the review reported is its
        candidate of the same persona, location and title; of several such candidates, the ones
        with its description, or all of them when none has it.
        """
        moved_from = finding.moved_from_candidate
        if moved_from is not None:
            return [moved_from] if 1 <= moved_from <= len(self._candidates) else []
        same = self._by_identity.get(_identity(finding), [])
        described = [n for n in same if self._candidates[n - 1].description == finding.description]
        return described if len(same) > 1 and described else list(same)

    def copy_of(self, number: int, reported: Sequence[SavedFinding]) -> int | None:
        """Where findings.json holds candidate `number`'s copy, if it holds one.

        A copy that reports other candidates as well, which nothing tells apart from this one,
        is refused: the verdict goes to that finding with `--index`, which records it on each.
        """
        copies = [i for i, f in enumerate(reported) if number in self.candidates_of(f)]
        if not copies:
            return None
        shared = sorted({n for i in copies for n in self.candidates_of(reported[i])})
        if len(copies) > 1 or len(shared) > 1:
            raise ValidationError(
                MESSAGES.review.candidate_copy_ambiguous.format(
                    number=copies[0] + 1, candidates=", ".join(f"#{n}" for n in shared)
                ),
                field="candidate",
            )
        return copies[0]


def _mirrored(target: SavedFinding, judged: SavedFinding) -> SavedFinding:
    """`target`, a finding's copy in the other session file, with the verdict `judged` was given."""
    return target.model_copy(update=judged.model_dump(include=set(_VERDICT_FIELDS)))


def _verdict_reason(finding: SavedFinding, status: str, reason: str) -> str:
    if reason:
        return reason
    if finding.invalidation_reason:
        return finding.invalidation_reason
    if finding.mitigating_mechanism:
        return finding.mitigating_mechanism
    return "Mitigated" if status == CONST_STATUS_MITIGATED else ""
