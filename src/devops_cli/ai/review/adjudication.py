"""Verdicts given through `devops review verify` and the MCP `verify_finding` tool (#949).

A verdict names its finding by the number `devops review findings` shows: the finding's place in
findings.json or, for a candidate, in candidates.json, whatever status filter the listing applied.
candidates.json holds every finding the review raised, each with the machine's verdict, and
findings.json the ones it reported. A candidate given a VERIFIED or MITIGATED verdict moves into
findings.json, where reports and review history read it. A verdict on a finding in findings.json
is recorded on the candidate it reports too, and a verdict on a candidate on its copy, so the two
files agree. A candidate whose defect findings.json already reports under another title, because
consolidation merged it or kept another persona's report of it, is judged through that finding
instead.

Every verdict records its adjudicator, and only a person's verdict is ground truth: an agent's
verdict never replaces one. Only a person's INVALIDATED verdict teaches the learned catalog, and
only a person's MITIGATED verdict records the mitigation in the ledger. The finding keeps one id
for each catalog or ledger entry its verdicts created or added to, and a reset to UNVERIFIED
withdraws each: an entry other verdicts also recorded loses one count, and one nothing else
recorded is removed.

A verdict holds the session's lock from reading its files to writing them. When the files cannot
be written, each entry a person's verdict updated is put back as it was and each it created is
removed, and a reset withdraws the entries it released only once the files are written, so the
session, the catalog and the ledger agree.
"""

from __future__ import annotations

import fcntl
import logging
from collections import Counter, defaultdict
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from devops_cli.ai.review.common_hallucinations import (
    CommonHallucinationEntry,
    auto_record_invalidated_finding,
    load_common_hallucinations,
    save_common_hallucinations,
)
from devops_cli.ai.review.mitigations import (
    MitigatedFindingEntry,
    load_mitigated_findings,
    record_mitigated_finding,
    save_mitigated_findings,
)
from devops_cli.ai.review.verdicts import Adjudicator, apply_verdict
from devops_cli.ai.review_schema import (
    ReviewSessionPayload,
    SavedFinding,
    _are_findings_duplicate,
)
from devops_cli.config.constants import (
    CONST_REVIEW_VERDICT_LOCK_FILENAME,
    CONST_STATUS_INVALIDATED,
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
        "perimeter_files",
        "regression_test",
        "verification_note",
    }
)


@dataclass(frozen=True, slots=True)
class Verdict:
    """A verdict to record: its status, who gave it, and why."""

    status: str
    adjudicator: Adjudicator
    reason: str = ""
    perimeter: tuple[str, ...] = ()
    regression_test: str | None = None


@dataclass(slots=True)
class EntryIds:
    """Learned-catalog and mitigations-ledger entry ids, one for each verdict that recorded one."""

    learned: list[str] = field(default_factory=list)
    ledger: list[str] = field(default_factory=list)

    def take(self, finding: SavedFinding) -> None:
        """Take over the ids `finding` holds."""
        self.learned += finding.learned_catalog_ids
        self.ledger += finding.mitigation_ledger_ids
        finding.learned_catalog_ids = []
        finding.mitigation_ledger_ids = []

    def withdraw(self) -> None:
        """Withdraw one count of each entry; an entry at its last count is removed."""
        if self.learned:
            _withdraw_learned(Counter(self.learned))
        if self.ledger:
            _withdraw_mitigations(Counter(self.ledger))


class _Entry(Protocol):
    """A learned-catalog or ledger entry, which its id names."""

    @property
    def id(self) -> str: ...


@dataclass(slots=True)
class RecordedEntries:
    """The learned-catalog and ledger entries a person's verdict wrote, each as it was before.

    None stands for an entry the verdict created.
    """

    learned: dict[str, CommonHallucinationEntry | None] = field(default_factory=dict)
    ledger: dict[str, MitigatedFindingEntry | None] = field(default_factory=dict)

    def restore(self) -> None:
        """Put back each entry the verdict updated as it was, and remove each it created."""
        if self.learned:
            learned = load_common_hallucinations(include_builtin=False)
            save_common_hallucinations(_restored(learned, self.learned))
        if self.ledger:
            save_mitigated_findings(_restored(load_mitigated_findings(), self.ledger))


@dataclass(slots=True)
class EntryChanges:
    """What the verdicts on a session change in the learned catalog and the mitigations ledger.

    A person's verdict records its entries before the session files are written, so the files
    hold their ids, and `undo` puts each back as it was when the files cannot be written. A
    reset releases the ids its findings held, and `settle` withdraws them once the files no
    longer hold them.
    """

    recorded: RecordedEntries = field(default_factory=RecordedEntries)
    released: EntryIds = field(default_factory=EntryIds)

    def undo(self) -> None:
        _logged(self.recorded.restore)

    def settle(self) -> None:
        _logged(self.released.withdraw)


@contextmanager
def adjudicating(session_dir: Path) -> Iterator[EntryChanges]:
    """Hold the session's verdict lock while a verdict reads, judges and writes its files.

    Verdicts given on one session at once, as an MCP client's parallel calls give them, take
    turns instead of writing over each other. The changes the verdict makes to the catalog and
    ledger are settled when the block completes and undone when it raises.
    """
    with (session_dir / CONST_REVIEW_VERDICT_LOCK_FILENAME).open("a", encoding="utf-8") as lock:
        # Closing the lock file releases the lock.
        fcntl.flock(lock, fcntl.LOCK_EX)
        changes = EntryChanges()
        try:
            yield changes
        except BaseException:
            changes.undo()
            raise
        changes.settle()


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
    changes: EntryChanges,
) -> None:
    """Record `verdict` on finding `number` of findings.json and on each candidate it reports.

    The finding holds the catalog and ledger records, and its candidates take the verdict.
    """
    finding = numbered_finding(reported.findings, number)
    pool = candidates.findings if candidates is not None else []
    mirrors = _CandidateIndex(pool).candidates_of(finding)
    for n in mirrors:
        _refuse_agent_over_person(pool[n - 1], verdict)
    _record_verdict(finding, verdict, changes)
    for n in mirrors:
        pool[n - 1] = _mirrored(pool[n - 1], finding, changes)
        _move_records(pool[n - 1], finding)


def judge_candidate(
    candidates: ReviewSessionPayload,
    reported: ReviewSessionPayload,
    number: int,
    verdict: Verdict,
    changes: EntryChanges,
) -> bool:
    """Record `verdict` on candidate `number`, keeping findings.json in step; True if it moved.

    The candidate's copy in findings.json takes the verdict too. Without a copy, a VERIFIED or
    MITIGATED verdict adds one, unless findings.json reports the candidate's defect under another
    title. The copy holds the catalog and ledger records of both, so a reset of either withdraws
    each record once.
    """
    candidate = numbered_finding(candidates.findings, number, field="candidate")
    copy_at = _CandidateIndex(candidates.findings).copy_of(number, reported.findings)
    if copy_at is not None:
        _refuse_agent_over_person(reported.findings[copy_at], verdict)
    elif verdict.status in _REPORTED_VERDICTS:
        _refuse_reported_elsewhere(reported.findings, candidate, number)
    _record_verdict(candidate, verdict, changes)
    if copy_at is not None:
        copy = _mirrored(reported.findings[copy_at], candidate, changes)
        _move_records(candidate, copy)
        reported.findings[copy_at] = copy
        return False
    if candidate.status not in _REPORTED_VERDICTS:
        return False
    moved = candidate.model_copy(
        update={
            "learned_catalog_ids": [],
            "mitigation_ledger_ids": [],
            "moved_from_candidate": number,
        },
        deep=True,
    )
    _move_records(candidate, moved)
    reported.findings.append(moved)
    return True


def _record_verdict(finding: SavedFinding, verdict: Verdict, changes: EntryChanges) -> None:
    """Apply `verdict` to `finding`, with what it writes outside the session.

    An agent's verdict on a finding a person judged is refused. A reset to UNVERIFIED releases
    what the finding's earlier verdicts recorded in the catalog and ledger, for `changes` to
    withdraw once the session is written. Any other verdict keeps those records, so a later
    reset still withdraws them.
    """
    _refuse_agent_over_person(finding, verdict)
    if verdict.status == CONST_STATUS_UNVERIFIED:
        changes.released.take(finding)
    mitigated = verdict.status == CONST_STATUS_MITIGATED
    perimeter = _mitigated_perimeter(finding, verdict.perimeter) if mitigated else []
    reason = _verdict_reason(finding, verdict.status, verdict.reason)
    apply_verdict(
        finding,
        verdict.status,
        by=None if verdict.status == CONST_STATUS_UNVERIFIED else verdict.adjudicator.value,
        reason=reason,
        mitigating_mechanism=reason if mitigated else None,
        perimeter_files=perimeter if mitigated else None,
        regression_test=verdict.regression_test if mitigated else None,
    )
    if verdict.adjudicator is Adjudicator.HUMAN:
        _record_entries(
            finding, verdict.status, reason, perimeter, verdict.regression_test, changes.recorded
        )


def _refuse_agent_over_person(finding: SavedFinding, verdict: Verdict) -> None:
    """An agent's verdict never replaces a person's, the ground truth history ranks on.

    Only a person's verdicts hold catalog and ledger records, so no agent's reset withdraws one.
    """
    if verdict.adjudicator is Adjudicator.AGENT and finding.verified_by == CONST_VERIFIED_BY_HUMAN:
        raise ValidationError(MESSAGES.review.agent_over_person, field="adjudicator")


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


def _mirrored(target: SavedFinding, judged: SavedFinding, changes: EntryChanges) -> SavedFinding:
    """`target`, a finding's copy in the other session file, with the verdict `judged` was given.

    A reset releases the records `target` held as well; any other verdict leaves them for the
    caller to move to the finding that holds both findings' records.
    """
    mirrored = target.model_copy(update=judged.model_dump(include=set(_VERDICT_FIELDS)))
    if judged.status == CONST_STATUS_UNVERIFIED:
        changes.released.take(mirrored)
    return mirrored


def _move_records(source: SavedFinding, holder: SavedFinding) -> None:
    """Move `source`'s catalog and ledger records to `holder`, so one finding holds each."""
    holder.learned_catalog_ids = [*holder.learned_catalog_ids, *source.learned_catalog_ids]
    holder.mitigation_ledger_ids = [*holder.mitigation_ledger_ids, *source.mitigation_ledger_ids]
    source.learned_catalog_ids = []
    source.mitigation_ledger_ids = []


def _mitigated_perimeter(finding: SavedFinding, perimeter: Sequence[str]) -> list[str]:
    """The files a mitigation guards: as given, else the finding's, else the cited file."""
    clean = [p.strip() for p in perimeter if p.strip()]
    if clean:
        return clean
    if finding.perimeter_files:
        return list(finding.perimeter_files)
    loc_file = finding.location.split(":")[0].strip() if finding.location else ""
    return [loc_file] if loc_file else []


def _verdict_reason(finding: SavedFinding, status: str, reason: str) -> str:
    if reason:
        return reason
    if finding.invalidation_reason:
        return finding.invalidation_reason
    if finding.mitigating_mechanism:
        return finding.mitigating_mechanism
    return "Mitigated" if status == CONST_STATUS_MITIGATED else ""


def _record_entries(
    finding: SavedFinding,
    status: str,
    reason: str,
    perimeter: list[str],
    regression_test: str | None,
    recorded: RecordedEntries,
) -> None:
    """Record what a person's verdict teaches, keeping the id of the entry it wrote.

    `recorded` keeps the entry as it was before, for `undo` to put back. The verdict stands when
    the catalog or ledger cannot be written, as it always has.
    """
    try:
        if status == CONST_STATUS_INVALIDATED:
            learned = {e.id: e for e in load_common_hallucinations(include_builtin=False)}
            entry = auto_record_invalidated_finding(finding, reason=reason)
            # A builtin entry that already covers the finding is left as it is.
            if entry is not None and entry.source != "builtin":
                finding.learned_catalog_ids = [*finding.learned_catalog_ids, entry.id]
                recorded.learned.setdefault(entry.id, learned.get(entry.id))
        elif status == CONST_STATUS_MITIGATED:
            ledger = {e.id: e for e in load_mitigated_findings()}
            mitigation = record_mitigated_finding(
                finding, reason=reason, perimeter_files=perimeter, regression_test=regression_test
            )
            finding.mitigation_ledger_ids = [*finding.mitigation_ledger_ids, mitigation.id]
            recorded.ledger.setdefault(mitigation.id, ledger.get(mitigation.id))
    except Exception as exc:
        logger.warning("Could not record the verdict in the catalog or ledger: %s", exc)


def _logged(step: Callable[[], None]) -> None:
    """Run `step`; the session already says what it should, so a failure is only logged."""
    try:
        step()
    except Exception as exc:
        logger.warning("Could not update the catalog or ledger after the verdict: %s", exc)


def _restored[E: _Entry](entries: Sequence[E], before: Mapping[str, E | None]) -> list[E]:
    """`entries` with each one `before` holds put back as it was, or removed where it is None."""
    restored: list[E] = []
    for entry in entries:
        if entry.id not in before:
            restored.append(entry)
        elif (prior := before[entry.id]) is not None:
            restored.append(prior)
    return restored


def _withdraw_learned(withdrawn: Counter[str]) -> None:
    """An entry other verdicts also recorded loses one count, and one nothing else recorded goes.

    A re-review's verdict adds to the learned entry the first review's verdict created.
    """
    learned = load_common_hallucinations(include_builtin=False)
    if not any(e.id in withdrawn for e in learned):
        return
    save_common_hallucinations(
        [
            e.model_copy(update={"occurrence_count": e.occurrence_count - withdrawn[e.id]})
            for e in learned
            if e.occurrence_count > withdrawn[e.id]
        ]
    )


def _withdraw_mitigations(withdrawn: Counter[str]) -> None:
    """As `_withdraw_learned`: two findings of one title in one file share a ledger entry."""
    ledger = load_mitigated_findings()
    if not any(e.id in withdrawn for e in ledger):
        return
    save_mitigated_findings(
        [
            e.model_copy(update={"verdict_count": e.verdict_count - withdrawn[e.id]})
            for e in ledger
            if e.verdict_count > withdrawn[e.id]
        ]
    )
