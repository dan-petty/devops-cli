"""Score saved review sessions against a label file, offline (#1138).

A label file names the inputs that were reviewed and labels the distinct findings their reviews
reported. A label holds the finding's identity, its label (valid-strict, valid-lenient, opinion or
false), the defect it is, the severity it should have, a note, its labeller and the date; an input
is either a tuning or a held-out input. Every figure the scorer reports is a ratio with its n, and
a ratio over a row no label covers reads "not computable" until a person labels the row.

A row's identity is:
- in a session the label file maps row by row, the cluster its row map names;
- otherwise the findings.sarif result at the row's cited file and line: its `fingerprint_v2`
  partial fingerprint, else the tool, rule, path and line or object the loop study keyed its
  clusters on; results of more than one tool, rule or fingerprint at that place leave the row
  without an identity, since only its title, which is never read, tells which one it is;
- otherwise, for a model's row, the one label of the row's path and origin page whose lines lie
  within five of the row's.

Nothing is parsed from a title or a message. A stored absolute path is made relative to the
checkout its input records, a row outside the session's reviewed tree (its `files/` pages) counts
as false without a lookup, and a row raised on a fixture page is no recall. Stability compares the
sessions of one input digest: the mean pairwise Jaccard of the identities they report, and
Fleiss' κ of their statuses over the identities every one of them reported. A session that records
no input digest is compared with no other.
"""

from __future__ import annotations

import itertools
import statistics
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator
from pydantic import ValidationError as PydanticValidationError

from devops_cli.ai.review.history import HistoryFinding, HistoryPayload
from devops_cli.ai.review.path_classes import is_fixture_path
from devops_cli.ai.review.profile import ReviewProfile
from devops_cli.ai.review_schema import _parse_location
from devops_cli.ai.run_store import digest
from devops_cli.config.constants import (
    CONST_GIT_DIR_NAME,
    CONST_REVIEW_FINDINGS_FILENAME,
    CONST_REVIEW_LABEL_FALSE,
    CONST_REVIEW_LABEL_VALID_STRICT,
    CONST_REVIEW_LABELS_VALID,
    CONST_REVIEW_PAGES_DIRNAME,
    CONST_REVIEW_PRODUCER_PERSONA,
    CONST_REVIEW_SARIF_FILENAME,
    CONST_REVIEW_SCORE_HIGH_SEVERITIES,
    CONST_REVIEW_SCORE_PERSONA_LINE_WINDOW,
    CONST_STATUS_VERIFIED,
)
from devops_cli.exceptions.validation import ValidationError
from devops_cli.git.operations import commit_snapshot
from devops_cli.security.normalization import NormalizedFinding, split_location
from devops_cli.security.sarif import SarifError, read_sarif

LabelValue = Literal["valid-strict", "valid-lenient", "opinion", "false"]
Split = Literal["tuning", "held-out"]
# A row's repository path, first and last cited line, and object.
_Place = tuple[str, int | None, int | None, str | None]
# The golden set's one commit: a fixed author, committer and date and no email address, so the
# same golden files always give the same commit, the one `git commit` makes of them.
GOLDEN_AUTHOR = "devops-cli golden"
GOLDEN_EMAIL = ""
GOLDEN_MESSAGE = "The golden review set's files, for a path review\n"
GOLDEN_DATE = datetime(2026, 10, 3, tzinfo=UTC)


class _LabelRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Identity(_LabelRecord):
    """What makes two findings one: its producer, rule and place, and the page that raised it."""

    key: str
    producer: str
    rule: str | None = None
    path: str
    start_line: int | None = None
    end_line: int | None = None
    # A kube-linter finding's object, such as `DaemonSet/ollama-16gib`.
    object: str | None = None
    # The page whose review raised it: its own path, or the fixture page it was echoed from.
    origin: str
    fingerprint_v2: str | None = None


class Label(_LabelRecord):
    """A person's call on one distinct finding."""

    identity: Identity
    label: LabelValue
    defect_id: str
    expected_severity: str | None = None
    note: str
    labeller: str
    date: date


class AcceptedLoss(_LabelRecord):
    """A defect of an input that no tool can express, so missing it is no recall loss to fix."""

    defect_id: str
    reason: str


class LabelledInput(_LabelRecord):
    """An input reviews ran on: its page digests, its checkout and the sessions mapped by row."""

    name: str
    split: Split
    digests: list[str] = Field(default_factory=list)
    # The checkout the input's sessions stored absolute paths under.
    root: str = ""
    # The golden findings file whose `files` this input reviews, relative to the label file.
    source: str | None = None
    known_defects: list[str] = Field(default_factory=list)
    accepted_loss: list[AcceptedLoss] = Field(default_factory=list)
    # Session id -> the label key of each findings.json row, in order.
    sessions: dict[str, list[str]] = Field(default_factory=dict)


class LabelFile(_LabelRecord):
    """Labelled inputs and their labels; paths in it are relative to the file."""

    about: str = ""
    recall_set: str | None = None
    inputs: list[LabelledInput]
    labels: list[Label]

    @model_validator(mode="after")
    def _row_maps_name_labels(self) -> LabelFile:
        keys = {label.identity.key for label in self.labels}
        named = {key for i in self.inputs for rows in i.sessions.values() for key in rows}
        if missing := sorted(named - keys):
            raise ValueError(f"row maps name keys no label holds: {', '.join(missing[:10])}")
        return self


def load_label_file(path: Path) -> LabelFile:
    """Read a label file, refusing one that does not parse or names a key no label holds."""
    try:
        return LabelFile.model_validate_json(path.read_bytes())
    except (OSError, PydanticValidationError) as exc:
        raise ValidationError(f"Cannot read label file {path}: {exc}", field="labels") from exc


class Ratio(BaseModel):
    """A count over its n; `reason` says why it is not computable."""

    numerator: int = 0
    denominator: int = 0
    reason: str | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def value(self) -> float | None:
        """The ratio, or None while it is not computable or has no n."""
        return None if self.reason or not self.denominator else self.numerator / self.denominator

    def __str__(self) -> str:
        if self.reason:
            return f"not computable ({self.reason})"
        if self.value is None:
            return "0/0"
        return f"{self.numerator}/{self.denominator} ({self.value:.1%})"


class Agreement(BaseModel):
    """A stability statistic over its n: session pairs for Jaccard, identities for κ."""

    value: float | None = None
    n: int = 0
    reason: str | None = None


class ProducerScore(BaseModel):
    """Precision of one producer's rows."""

    rows: int
    lenient: Ratio
    strict: Ratio
    distinct: Ratio


class SessionScore(BaseModel):
    """One session's figures."""

    session: str
    input: str
    digest: str
    rows: int
    lenient: Ratio
    strict: Ratio
    distinct: Ratio
    verified: Ratio
    verified_strict: Ratio
    high: Ratio
    by_producer: dict[str, ProducerScore]
    recall_set: Ratio
    known_defects: Ratio
    llm_calls: int | None = None
    prompt_tokens: int | None = None
    wall_seconds: float | None = None


class GroupScore(BaseModel):
    """The sessions of one input digest, pooled, and how much they agree."""

    digest: str
    input: str
    split: Split | None = None
    sessions: int
    lenient: Ratio
    strict: Ratio
    jaccard: Agreement
    kappa: Agreement


class RecallEntry(BaseModel):
    """A finding of the recall set and the sessions whose report cites it."""

    location: str
    reported_in: int
    sessions: int


class UnlabelledRow(BaseModel):
    """A row no label covers: a person labels it, and the ratios over it become computable."""

    session: str
    row: int
    location: str
    producer: str
    identity: str | None = None


class ScoreReport(BaseModel):
    """Every scored session, each input's pooled figures, recall and the rows left to label."""

    labels_digest: str
    sessions: list[SessionScore]
    groups: list[GroupScore]
    recall_set: list[RecallEntry]
    unlabelled: list[UnlabelledRow]

    def run_metrics(self) -> dict[str, Any]:
        """The top-level figures `devops ai runs check` compares, and why each other one is not.

        A figure that is not computable is left out, and `not_computable` names it with its
        reason, so the check fails a run that cannot compute a figure its baseline recorded.
        """
        sessions = self.sessions
        gated: dict[str, tuple[float | None, str | None]] = {
            "precision_lenient": _figure(_pooled([s.lenient for s in sessions])),
            "precision_strict": _figure(_pooled([s.strict for s in sessions])),
            "recall": _figure(_pooled([s.known_defects for s in sessions])),
            "stability_jaccard": _stability(self.groups, lambda g: g.jaccard),
            "stability_kappa": _stability(self.groups, lambda g: g.kappa),
        }
        medians = {
            "median_llm_calls": _median(s.llm_calls for s in sessions),
            "median_prompt_tokens": _median(s.prompt_tokens for s in sessions),
            "median_wall_seconds": _median(s.wall_seconds for s in sessions),
        }
        figures = {name: value for name, (value, _) in gated.items()} | medians
        return {
            **{name: round(value, 4) for name, value in figures.items() if value is not None},
            "not_computable": {
                name: reason for name, (value, reason) in gated.items() if value is None
            },
        }


class GoldenRepository(BaseModel):
    """The golden set written out as a repository, and the defects no tool can express."""

    path: str
    commit: str
    files: int
    accepted_loss: list[AcceptedLoss]


class _PageFinding(BaseModel):
    location: str = ""


class _SessionPage(BaseModel):
    file_path: str
    findings: list[_PageFinding] = Field(default_factory=list)


class _RecallFinding(BaseModel):
    path: str
    lines: tuple[int, int]


class _RecallSet(BaseModel):
    findings: list[_RecallFinding]


class _GoldenSet(BaseModel):
    files: dict[str, str]


@dataclass(frozen=True, slots=True)
class _Row:
    """A findings.json row as the scorer reads it."""

    session: str
    number: int
    location: str
    path: str
    start: int | None
    end: int | None
    status: str
    severity: str
    producer: str
    origin: str
    in_tree: bool
    identity: str | None
    label: Label | None

    @property
    def verdict(self) -> str | None:
        """The row's label; false outside the reviewed tree; None when no label covers it."""
        if not self.in_tree:
            return CONST_REVIEW_LABEL_FALSE
        return self.label.label if self.label is not None else None

    @property
    def defect(self) -> str:
        return self.label.defect_id if self.label else (self.identity or self.location)

    @property
    def valid(self) -> bool:
        return self.verdict in CONST_REVIEW_LABELS_VALID

    @property
    def strict(self) -> bool:
        return self.verdict == CONST_REVIEW_LABEL_VALID_STRICT


@dataclass(frozen=True, slots=True)
class _LabelIndex:
    by_key: dict[str, Label]
    by_fingerprint: dict[str, Label]
    by_tool_key: dict[tuple[str, str | None, str, int | str | None], Label]
    persona: dict[tuple[str, str], list[Label]]

    @classmethod
    def of(cls, labels: Sequence[Label]) -> _LabelIndex:
        persona: dict[tuple[str, str], list[Label]] = {}
        for label in labels:
            if label.identity.producer == CONST_REVIEW_PRODUCER_PERSONA:
                persona.setdefault((label.identity.path, label.identity.origin), []).append(label)
        return cls(
            by_key={label.identity.key: label for label in labels},
            by_fingerprint={
                label.identity.fingerprint_v2: label
                for label in labels
                if label.identity.fingerprint_v2
            },
            by_tool_key={_label_tool_key(label.identity): label for label in labels},
            persona=persona,
        )


@dataclass(frozen=True, slots=True)
class _Session:
    """A saved session's rows and the files around them."""

    path: Path
    digest: str
    findings: tuple[HistoryFinding, ...]
    tree: frozenset[str]
    # Each location a page raised -> that page.
    origins: dict[str, str]
    # Each place findings.sarif names -> every result there.
    sarif: dict[tuple[str, int | str | None], list[NormalizedFinding]]
    profile: ReviewProfile | None


# =============================================================================
# Reading
# =============================================================================


def _read_session(session_dir: Path) -> _Session:
    """A saved session; one without a readable findings.json, or with a page that does not
    parse, is refused rather than scored as a session that reported nothing."""
    try:
        record = HistoryPayload.model_validate_json(
            (session_dir / CONST_REVIEW_FINDINGS_FILENAME).read_bytes()
        )
        pages = [
            _SessionPage.model_validate_json(page.read_bytes())
            for page in sorted((session_dir / CONST_REVIEW_PAGES_DIRNAME).glob("*.json"))
        ]
    except (OSError, PydanticValidationError) as exc:
        raise ValidationError(
            f"Cannot read review session {session_dir}: {exc}", field="session"
        ) from exc
    origins: dict[str, str] = {}
    for page in pages:
        for finding in page.findings:
            origins.setdefault(finding.location, page.file_path)
    sarif: dict[tuple[str, int | str | None], list[NormalizedFinding]] = {}
    for result in _sarif_results(session_dir):
        sarif.setdefault(_result_key(result.path, result.line, result.symbol), []).append(result)
    return _Session(
        path=session_dir,
        digest=record.subject.get("input", ""),
        findings=tuple(record.findings),
        tree=frozenset(page.file_path for page in pages),
        origins=origins,
        sarif=sarif,
        profile=ReviewProfile.load(session_dir),
    )


def _sarif_results(session_dir: Path) -> list[NormalizedFinding]:
    sarif = session_dir / CONST_REVIEW_SARIF_FILENAME
    if not sarif.is_file():
        return []
    try:
        return read_sarif(sarif)
    except SarifError as exc:
        raise ValidationError(f"{sarif} is not SARIF: {exc}", field="session") from exc


def _read_recall_set(label_file: LabelFile, labels_path: Path) -> list[_RecallFinding]:
    if label_file.recall_set is None:
        return []
    source = labels_path.parent / label_file.recall_set
    try:
        return _RecallSet.model_validate_json(source.read_bytes()).findings
    except (OSError, PydanticValidationError) as exc:
        raise ValidationError(f"Cannot read recall set {source}: {exc}", field="labels") from exc


# =============================================================================
# Identity
# =============================================================================


def _result_key(path: str, line: int | None, obj: str | None) -> tuple[str, int | str | None]:
    return path, line if line is not None else obj


def _label_tool_key(identity: Identity) -> tuple[str, str | None, str, int | str | None]:
    return (identity.producer, identity.rule, identity.path, identity.object or identity.start_line)


def _relative(path: str, root: str) -> str:
    """A stored absolute path under the input's checkout, as a repository path."""
    pure = PurePosixPath(path)
    if root and pure.is_absolute() and pure.is_relative_to(root):
        return pure.relative_to(root).as_posix()
    return path


def _place(finding: HistoryFinding, root: str) -> _Place:
    """The repository path, first and last line, and object a row's location cites."""
    path, start, end = _parse_location(finding.location)
    obj = None
    if start is None:
        path, _, obj = split_location(finding.location)
    if finding.cited_code is not None:
        return finding.cited_code.file, start or finding.cited_code.line, end, obj
    return _relative(path, root), start, end, obj


def _within_window(label: Label, start: int | None, end: int | None) -> bool:
    first = label.identity.start_line
    if start is None or first is None:
        return False
    last = label.identity.end_line or first
    gap = max(first - (end or start), start - last, 0)
    return gap <= CONST_REVIEW_SCORE_PERSONA_LINE_WINDOW


def _persona_label(
    index: _LabelIndex, path: str, origin: str, start: int | None, end: int | None
) -> Label | None:
    """The one persona label near the row; none when no label, or more than one, is near."""
    near = [lab for lab in index.persona.get((path, origin), []) if _within_window(lab, start, end)]
    return near[0] if len(near) == 1 else None


def _tool_label(
    index: _LabelIndex, results: Sequence[NormalizedFinding]
) -> tuple[str | None, Label | None]:
    """A tool row's identity and label: by fingerprint, else by the loop's cluster key.

    The results at the row's place that differ in tool, rule or fingerprint leave it with
    neither, as two persona labels near a model's row do; identical duplicates are one result.
    """
    kinds = {(r.tool, r.rule_id, r.partial_fingerprints.get("fingerprint_v2")) for r in results}
    if len(kinds) > 1:
        return None, None
    result = results[0]
    fingerprint = result.partial_fingerprints.get("fingerprint_v2")
    label = index.by_fingerprint.get(fingerprint or "") or index.by_tool_key.get(
        (result.tool, result.rule_id, result.path, result.symbol or result.line)
    )
    return (label.identity.key if label else fingerprint), label


def _row(
    session: _Session,
    number: int,
    finding: HistoryFinding,
    place: tuple[str, int | None, int | None],
    found: tuple[str, str | None, Label | None, str],
) -> _Row:
    """A row; one outside the reviewed tree keeps its identity but matches no label."""
    path, start, end = place
    producer, identity, label, origin = found
    in_tree = path in session.tree
    return _Row(
        session=session.path.name,
        number=number,
        location=finding.location,
        path=path,
        start=start,
        end=end,
        status=finding.status,
        severity=finding.severity.upper(),
        producer=producer,
        origin=origin,
        in_tree=in_tree,
        identity=identity,
        label=label if in_tree else None,
    )


def _mapped_rows(session: _Session, keys: list[str], index: _LabelIndex, root: str) -> list[_Row]:
    """Rows of a session the label file maps row by row: each row's cluster is its identity."""
    if len(keys) != len(session.findings):
        raise ValidationError(
            f"Session {session.path.name} holds {len(session.findings)} findings.json rows, but "
            f"its row map names {len(keys)} rows.",
            field="labels",
        )
    rows = []
    for number, (finding, key) in enumerate(zip(session.findings, keys, strict=True), start=1):
        label = index.by_key[key]
        path, start, end, _ = _place(finding, root)
        found = (label.identity.producer, key, label, label.identity.origin)
        rows.append(_row(session, number, finding, (path, start, end), found))
    return rows


def _found(
    session: _Session, index: _LabelIndex, finding: HistoryFinding, place: _Place
) -> tuple[str, str | None, Label | None, str]:
    """A new session's row: its producer, identity, label and origin page."""
    path, start, end, obj = place
    origin = session.origins.get(finding.location, path)
    results = session.sarif.get(_result_key(path, start, obj))
    if results:
        identity, label = _tool_label(index, results)
        return "+".join(sorted({r.tool for r in results})), identity, label, origin
    label = _persona_label(index, path, origin, start, end)
    return CONST_REVIEW_PRODUCER_PERSONA, label.identity.key if label else None, label, origin


def _new_rows(session: _Session, index: _LabelIndex, root: str) -> list[_Row]:
    """Rows of any other session: identity from findings.sarif, else the persona window."""
    rows = []
    for number, finding in enumerate(session.findings, start=1):
        place = _place(finding, root)
        found = _found(session, index, finding, place)
        rows.append(_row(session, number, finding, place[:3], found))
    return rows


# =============================================================================
# Figures
# =============================================================================


def _ratio(rows: Sequence[_Row], counts: Callable[[_Row], bool]) -> Ratio:
    """How many rows count, over the rows; not computable while a row has no label."""
    unlabelled = sum(row.verdict is None for row in rows)
    counted = sum(counts(row) for row in rows if row.verdict is not None)
    reason = f"{unlabelled} of {len(rows)} rows unlabelled" if unlabelled else None
    return Ratio(numerator=counted, denominator=len(rows), reason=reason)


def _pooled(ratios: Sequence[Ratio]) -> Ratio:
    reasons = [r.reason for r in ratios if r.reason]
    return Ratio(
        numerator=sum(r.numerator for r in ratios),
        denominator=sum(r.denominator for r in ratios),
        reason=f"{len(reasons)} of {len(ratios)} sessions not computable" if reasons else None,
    )


def _distinct(rows: Sequence[_Row]) -> Ratio:
    """Valid distinct defects over the distinct defects the rows report."""
    base = _ratio(rows, lambda row: row.valid)
    defects = {row.defect for row in rows}
    valid = {row.defect for row in rows if row.valid}
    return Ratio(numerator=len(valid), denominator=len(defects), reason=base.reason)


def _known_defects(rows: Sequence[_Row], known: Sequence[str]) -> Ratio:
    """The input's known defects a row reports from the defect's own page, not a fixture echo."""
    if not known:
        return Ratio(reason="the input lists no known defects")
    base = _ratio(rows, lambda row: row.valid)
    found = {row.defect for row in rows if row.valid and not is_fixture_path(row.origin)}
    return Ratio(numerator=len(found & set(known)), denominator=len(known), reason=base.reason)


def _cites(row: _Row, entry: _RecallFinding) -> bool:
    """A row in the reviewed tree, raised on its own page, citing a line of the entry's range."""
    first, last = entry.lines
    return (
        row.in_tree
        and row.path == entry.path
        and row.start is not None
        and row.start <= last
        and (row.end or row.start) >= first
        and not is_fixture_path(row.origin)
    )


def _recall_hits(rows: Sequence[_Row], entries: Sequence[_RecallFinding]) -> list[bool]:
    return [any(_cites(row, entry) for row in rows) for entry in entries]


def _by_producer(rows: Sequence[_Row]) -> dict[str, ProducerScore]:
    producers = sorted({row.producer for row in rows})
    return {
        name: ProducerScore(
            rows=len(mine := [row for row in rows if row.producer == name]),
            lenient=_ratio(mine, lambda row: row.valid),
            strict=_ratio(mine, lambda row: row.strict),
            distinct=_distinct(mine),
        )
        for name in producers
    }


def _session_score(
    session: _Session,
    rows: Sequence[_Row],
    labelled: LabelledInput | None,
    entries: Sequence[_RecallFinding],
) -> SessionScore:
    verified = [row for row in rows if row.status == CONST_STATUS_VERIFIED]
    high = [row for row in rows if row.severity in CONST_REVIEW_SCORE_HIGH_SEVERITIES]
    hits = _recall_hits(rows, entries)
    profile = session.profile
    return SessionScore(
        session=session.path.name,
        input=labelled.name if labelled else session.digest,
        digest=session.digest,
        rows=len(rows),
        lenient=_ratio(rows, lambda row: row.valid),
        strict=_ratio(rows, lambda row: row.strict),
        distinct=_distinct(rows),
        verified=_ratio(verified, lambda row: row.valid),
        verified_strict=_ratio(verified, lambda row: row.strict),
        high=_ratio(high, lambda row: row.valid),
        by_producer=_by_producer(rows),
        recall_set=Ratio(numerator=sum(hits), denominator=len(hits)),
        known_defects=_known_defects(rows, labelled.known_defects if labelled else ()),
        llm_calls=profile.llm_calls if profile else None,
        prompt_tokens=profile.prompt_tokens if profile else None,
        wall_seconds=profile.total_wall_seconds if profile else None,
    )


def _jaccard(identities: Sequence[set[str]], missing: int) -> Agreement:
    if len(identities) < 2:
        return Agreement(reason="one session")
    if missing:
        return Agreement(reason=f"{missing} rows have no identity")
    pairs = list(itertools.combinations(identities, 2))
    values = [len(a & b) / len(a | b) if a | b else 1.0 for a, b in pairs]
    return Agreement(value=statistics.fmean(values), n=len(pairs))


def _kappa(statuses: Sequence[dict[str, str]], missing: int) -> Agreement:
    """Fleiss' κ of the sessions' statuses over the identities every session reported.

    statsmodels' `fleiss_kappa` needs as many ratings for every subject, so an identity some
    session did not report is left out rather than rated as absent.
    """
    if len(statuses) < 2:
        return Agreement(reason="one session")
    if missing:
        return Agreement(reason=f"{missing} rows have no identity")
    common = sorted(set.intersection(*(set(s) for s in statuses)))
    ratings = [[session[identity] for session in statuses] for identity in common]
    categories = {rating for subject in ratings for rating in subject}
    if not common:
        return Agreement(reason="no identity every session reported")
    if len(categories) < 2:
        return Agreement(n=len(common), reason=f"every rating is {categories.pop()}")
    from statsmodels.stats.inter_rater import aggregate_raters, fleiss_kappa

    table, _ = aggregate_raters(ratings)
    return Agreement(value=float(fleiss_kappa(table, method="fleiss")), n=len(common))


def _group_score(
    group_digest: str,
    scored: Sequence[tuple[SessionScore, list[_Row]]],
    labelled: LabelledInput | None,
) -> GroupScore:
    sessions = [rows for _, rows in scored]
    missing = sum(row.identity is None for rows in sessions for row in rows)
    if group_digest:
        jaccard = _jaccard([{row.identity or "" for row in rows} for rows in sessions], missing)
        kappa = _kappa([_first_status(rows) for rows in sessions], missing)
    else:
        jaccard = kappa = Agreement(reason="the session records no input digest")
    return GroupScore(
        digest=group_digest,
        input=labelled.name if labelled else (group_digest or scored[0][0].session),
        split=labelled.split if labelled else None,
        sessions=len(scored),
        lenient=_pooled([score.lenient for score, _ in scored]),
        strict=_pooled([score.strict for score, _ in scored]),
        jaccard=jaccard,
        kappa=kappa,
    )


def _first_status(rows: Sequence[_Row]) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for row in rows:
        statuses.setdefault(row.identity or "", row.status)
    return statuses


def _figure(ratio: Ratio) -> tuple[float | None, str | None]:
    """A pooled ratio as a run figure, or why it is not computable."""
    if ratio.value is None:
        return None, ratio.reason or "no rows"
    return ratio.value, None


def _stability(
    groups: Sequence[GroupScore], statistic: Callable[[GroupScore], Agreement]
) -> tuple[float | None, str | None]:
    """The mean of a statistic over the inputs with two or more sessions, while each has it."""
    compared = [g for g in groups if g.sessions > 1]
    if not compared:
        return None, "no input has two sessions"
    values = []
    for group in compared:
        agreement = statistic(group)
        if agreement.value is None:
            return None, f"input {group.input}: {agreement.reason}"
        values.append(agreement.value)
    return statistics.fmean(values), None


def _median(values: Iterable[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return float(statistics.median(present)) if present else None


# =============================================================================
# Scoring
# =============================================================================


def _input_of(label_file: LabelFile, session: _Session) -> LabelledInput | None:
    """The input a session belongs to: the one mapping it by row, else the one of its digest."""
    mapped = next((i for i in label_file.inputs if session.path.name in i.sessions), None)
    if mapped is not None and session.digest not in mapped.digests:
        raise ValidationError(
            f"Session {session.path.name} reviewed input {session.digest or 'unrecorded'}, "
            f"not input {mapped.name}, whose row map names it.",
            field="labels",
        )
    return mapped or next((i for i in label_file.inputs if session.digest in i.digests), None)


def score_sessions(session_dirs: Sequence[Path], labels_path: Path) -> ScoreReport:
    """Score saved review sessions against a label file; no model, network or scanner runs."""
    label_file = load_label_file(labels_path)
    index = _LabelIndex.of(label_file.labels)
    entries = _read_recall_set(label_file, labels_path)
    scored: list[tuple[SessionScore, list[_Row], LabelledInput | None]] = []
    for session_dir in session_dirs:
        session = _read_session(session_dir)
        labelled = _input_of(label_file, session)
        root = labelled.root if labelled else ""
        keys = labelled.sessions.get(session.path.name) if labelled else None
        rows = (
            _mapped_rows(session, keys, index, root)
            if keys is not None
            else _new_rows(session, index, root)
        )
        scored.append((_session_score(session, rows, labelled, entries), rows, labelled))
    return _report(label_file, scored, entries)


def _report(
    label_file: LabelFile,
    scored: Sequence[tuple[SessionScore, list[_Row], LabelledInput | None]],
    entries: Sequence[_RecallFinding],
) -> ScoreReport:
    groups: dict[tuple[str, str], list[tuple[SessionScore, list[_Row], LabelledInput | None]]] = {}
    for score, rows, labelled in scored:
        # Sessions group by input digest; a session that records none is a group of its own.
        key = (score.digest, "" if score.digest else score.session)
        groups.setdefault(key, []).append((score, rows, labelled))
    hits = [_recall_hits(rows, entries) for _, rows, _ in scored]
    return ScoreReport(
        labels_digest=digest(label_file.model_dump(mode="json")),
        sessions=[score for score, _, _ in scored],
        groups=[
            _group_score(group, [(score, rows) for score, rows, _ in items], items[0][2])
            for (group, _), items in groups.items()
        ],
        recall_set=[
            RecallEntry(
                location=f"{entry.path}:{entry.lines[0]}-{entry.lines[1]}",
                reported_in=sum(session[i] for session in hits),
                sessions=len(hits),
            )
            for i, entry in enumerate(entries)
        ],
        unlabelled=[
            UnlabelledRow(
                session=row.session,
                row=row.number,
                location=row.location,
                producer=row.producer,
                identity=row.identity,
            )
            for _, rows, _ in scored
            for row in rows
            if row.verdict is None
        ],
    )


# =============================================================================
# The golden set
# =============================================================================


def materialise_golden(labels_path: Path, destination: Path) -> GoldenRepository:
    """Write the golden input's files into a new repository with one fixed commit."""
    label_file = load_label_file(labels_path)
    golden = next((i for i in label_file.inputs if i.source), None)
    if golden is None or golden.source is None:
        raise ValidationError(f"{labels_path} names no golden input source.", field="labels")
    if destination.exists() and not destination.is_dir():
        raise ValidationError(f"{destination} is not a directory.", field="materialise_golden")
    if destination.exists() and any(destination.iterdir()):
        raise ValidationError(f"{destination} is not empty.", field="materialise_golden")
    source = labels_path.parent / golden.source
    try:
        files = _GoldenSet.model_validate_json(source.read_bytes()).files
    except (OSError, PydanticValidationError) as exc:
        raise ValidationError(f"Cannot read golden set {source}: {exc}", field="labels") from exc
    root = destination.resolve()
    targets = {rel_path: (root / rel_path).resolve() for rel_path in files}
    for rel_path, target in targets.items():
        if not target.is_relative_to(root):
            raise ValidationError(f"Golden file {rel_path} lies outside {root}.", field="labels")
        if CONST_GIT_DIR_NAME in target.relative_to(root).parts:
            raise ValidationError(
                f"Golden file {rel_path} lies in the repository's {CONST_GIT_DIR_NAME} directory.",
                field="labels",
            )
    for rel_path, target in targets.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(files[rel_path], encoding="utf-8")
    commit = commit_snapshot(
        root,
        list(files),
        GOLDEN_MESSAGE,
        author=GOLDEN_AUTHOR,
        email=GOLDEN_EMAIL,
        date=GOLDEN_DATE,
    )
    return GoldenRepository(
        path=str(root), commit=commit, files=len(files), accepted_loss=golden.accepted_loss
    )


__all__ = [
    "AcceptedLoss",
    "Agreement",
    "GoldenRepository",
    "GroupScore",
    "Identity",
    "Label",
    "LabelFile",
    "LabelledInput",
    "ProducerScore",
    "Ratio",
    "RecallEntry",
    "ScoreReport",
    "SessionScore",
    "UnlabelledRow",
    "load_label_file",
    "materialise_golden",
    "score_sessions",
]
