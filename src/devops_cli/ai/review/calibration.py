"""What a finding's evidence lets its severity be (#948).

In session `20261001-224227` 54% of candidates were HIGH, the value in both prompt examples, and
25 of 27 reported findings on tests were CRITICAL or HIGH. Once verification has given its
verdicts, each rule below caps a severity, none raises one, and a capped finding keeps the
severity it was given as `severity_raw`:

- CRITICAL requires VERIFIED.
- A hedged title ("Potential", "May", "Could") is MEDIUM at most, whoever verified it. Criteria
  settle no VERIFIED verdict, since a pass can check the opposite of the claim, and the
  verifier's confirmation is not evidence enough to lift the cap (#1043).
- A finding in a test or a document is LOW at most unless it concerns a verified secret. A
  secret scanner's match is that verification: a secret pasted into a task file or a changelog
  fragment is still a secret.

Calibration runs once, when the report is written. A later verdict through `devops review verify`
changes a finding's status, not its severity.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from pathlib import Path, PurePosixPath

from devops_cli.ai.review.category_metrics import resolve_finding_category
from devops_cli.ai.review.classification import FileContextType, classify_file_context
from devops_cli.ai.review_schema import DefectClass, Finding, less_severe
from devops_cli.config.constants import (
    CONST_REVIEW_HEDGE_WORDS,
    CONST_REVIEW_SECRET_SCAN_TITLE_PREFIXES,
    CONST_REVIEW_TEST_DIR_NAMES,
    CONST_REVIEW_TEST_STEM_SUFFIXES,
    CONST_SEVERITY_HIGH,
    CONST_SEVERITY_LOW,
    CONST_SEVERITY_MEDIUM,
    CONST_STATUS_INVALIDATED,
    CONST_STATUS_VERIFIED,
    CONST_TEST_FILE_PREFIX,
)

_WORDS = re.compile(r"[a-z]+")


def _cited_path(finding: Finding, root: Path | None) -> PurePosixPath:
    """The file a finding cites, relative to the repository `root`.

    Scanners cite absolute paths (#788), whose directories above the checkout say nothing about
    the file: a checkout under `tests/` made every scanner finding a test finding. An absolute
    path outside `root` is judged by its name alone.
    """
    path = PurePosixPath(finding.location.split(":", 1)[0].strip().replace("\\", "/"))
    if not path.is_absolute():
        return path
    if root is not None and path.is_relative_to(root.as_posix()):
        return path.relative_to(root.as_posix())
    return PurePosixPath(path.name)


def is_test_path(path: PurePosixPath) -> bool:
    """Whether a file is a test: under a test directory, or named as test runners collect."""
    return (
        path.name.startswith(CONST_TEST_FILE_PREFIX)
        or path.stem.endswith(CONST_REVIEW_TEST_STEM_SUFFIXES)
        or any(part in CONST_REVIEW_TEST_DIR_NAMES for part in path.parts[:-1])
    )


def _is_verified(finding: Finding, _path: PurePosixPath) -> bool:
    return finding.status == CONST_STATUS_VERIFIED


def _is_unverified(finding: Finding, path: PurePosixPath) -> bool:
    return not _is_verified(finding, path)


def _is_hedged(finding: Finding, _path: PurePosixPath) -> bool:
    return not CONST_REVIEW_HEDGE_WORDS.isdisjoint(_WORDS.findall(finding.title.lower()))


def _is_secret_scan_match(finding: Finding) -> bool:
    """Whether a secret scanner found it, Gitleaks or Trivy's secret rules, and it still stands.

    A review of routed files runs no verifier, so a secret it found could never be a verified
    one, and in a mixed review a fragment's secret the verifier left alone fell to LOW while
    the same secret in `src/` stayed HIGH.
    """
    return (
        finding.title.startswith(CONST_REVIEW_SECRET_SCAN_TITLE_PREFIXES)
        and finding.status != CONST_STATUS_INVALIDATED
    )


def _is_in_test_or_document(finding: Finding, path: PurePosixPath) -> bool:
    in_scope = (
        is_test_path(path) or classify_file_context(str(path)) is FileContextType.DOCUMENTATION
    )
    verified_secret = _is_secret_scan_match(finding) or (
        _is_verified(finding, path)
        and resolve_finding_category(finding) == DefectClass.SECRET_EXPOSURE.value
    )
    return in_scope and not verified_secret


# Each rule, given the finding and the file it cites, and the severity it caps the finding at.
_SEVERITY_CAPS: tuple[tuple[Callable[[Finding, PurePosixPath], bool], str], ...] = (
    (_is_unverified, CONST_SEVERITY_HIGH),
    (_is_hedged, CONST_SEVERITY_MEDIUM),
    (_is_in_test_or_document, CONST_SEVERITY_LOW),
)


def calibrate_severity[F: Finding](finding: F, root: Path | None = None) -> F:
    """The finding with its severity capped by every rule that applies to it; `root` is the
    repository an absolute cited path is read from."""
    path = _cited_path(finding, root)
    severity = finding.severity
    for applies, ceiling in _SEVERITY_CAPS:
        if applies(finding, path):
            severity = less_severe(severity, ceiling)
    if severity == finding.severity:
        return finding
    return finding.model_copy(
        update={"severity": severity, "severity_raw": finding.severity_raw or finding.severity}
    )


def calibrate_findings[F: Finding](findings: Iterable[F], root: Path | None = None) -> list[F]:
    """Each finding with its severity calibrated, cited paths read from the repository `root`."""
    return [calibrate_severity(finding, root) for finding in findings]
