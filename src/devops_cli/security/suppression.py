"""Suppression policy with cross-repository inheritance.

A suppression that cannot be inherited has to be copied into every repository that needs
it, and copies drift. A suppression that never expires is indistinguishable from a blind
spot: the reason it was added stops being true, and nothing ever revisits it.

Policies here compose through `extends` and every rule may carry an expiry. An expired
suppression stops suppressing, which is the property that keeps a policy file from quietly
becoming permanent.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

import yaml

from devops_cli.config.constants import CONST_SUPPRESSION_MAX_INHERITANCE_DEPTH
from devops_cli.security.normalization import NormalizedFinding

logger = logging.getLogger(__name__)


class SuppressionPolicyError(ValueError):
    """Raised when a suppression policy cannot be loaded."""


@dataclass(frozen=True)
class SuppressionRule:
    """One suppression, matched against a finding."""

    rule: str = "*"
    paths: tuple[str, ...] = ("*",)
    tools: tuple[str, ...] = ("*",)
    fingerprint: str | None = None
    reason: str = ""
    expires: date | None = None
    source: str = ""

    def is_expired(self, today: date | None = None) -> bool:
        """Report whether this suppression has lapsed."""
        if self.expires is None:
            return False
        return self.expires < (today or date.today())

    def matches(self, finding: NormalizedFinding, today: date | None = None) -> bool:
        """Report whether this rule suppresses a finding.

        An expired rule matches nothing. A fingerprint, when given, must match exactly and
        alone decides: it identifies one specific accepted finding, not a class of them.
        """
        if self.is_expired(today):
            return False
        if self.fingerprint is not None:
            return self.fingerprint == finding.fingerprint
        if not _any_match(self.tools, finding.tool):
            return False
        if not _any_match((self.rule,), finding.rule_id):
            return False
        return _any_match(self.paths, finding.path)


def _any_match(patterns: tuple[str, ...], value: str) -> bool:
    """Report whether a value matches any glob pattern."""
    return any(fnmatch(value, pattern) for pattern in patterns)


def _as_tuple(value: Any, default: tuple[str, ...]) -> tuple[str, ...]:
    """Coerce a scalar or sequence into a tuple of patterns."""
    if value is None:
        return default
    if isinstance(value, str):
        return (value,)
    if isinstance(value, list | tuple):
        return tuple(str(item) for item in value)
    return default


def _as_date(value: Any) -> date | None:
    """Parse an expiry date, treating an unparseable one as already expired.

    Defaulting an unreadable expiry to "never" would turn a typo into a permanent
    suppression, which is the failure this field exists to prevent.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError:
        logger.debug("Unparseable suppression expiry %r; treating as expired.", value)
        return date.min


@dataclass
class SuppressionPolicy:
    """An ordered set of suppression rules resolved from a policy file and its parents."""

    rules: list[SuppressionRule] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)

    def suppresses(
        self, finding: NormalizedFinding, today: date | None = None
    ) -> SuppressionRule | None:
        """Return the rule suppressing a finding, or ``None`` if none does."""
        for rule in self.rules:
            if rule.matches(finding, today):
                return rule
        return None

    def apply(
        self, findings: list[NormalizedFinding], today: date | None = None
    ) -> tuple[list[NormalizedFinding], list[tuple[NormalizedFinding, SuppressionRule]]]:
        """Partition findings into those that survive and those that were suppressed.

        Suppressed findings are returned rather than discarded so a report can state what it
        hid and on whose authority. A suppression no one can see is not a policy decision,
        it is a missing result.
        """
        kept: list[NormalizedFinding] = []
        suppressed: list[tuple[NormalizedFinding, SuppressionRule]] = []
        for finding in findings:
            rule = self.suppresses(finding, today)
            if rule is None:
                kept.append(finding)
            else:
                suppressed.append((finding, rule))
        return kept, suppressed

    def expired_rules(self, today: date | None = None) -> list[SuppressionRule]:
        """List rules that have lapsed, so a report can prompt for their review."""
        return [rule for rule in self.rules if rule.is_expired(today)]


def _parse_rules(document: Any, source: Path) -> list[SuppressionRule]:
    """Parse the `suppressions` array of one policy document."""
    entries = document.get("suppressions") if isinstance(document, dict) else None
    if entries is None:
        return []
    if not isinstance(entries, list):
        raise SuppressionPolicyError(f"'{source}': 'suppressions' must be a list")

    rules: list[SuppressionRule] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise SuppressionPolicyError(f"'{source}': each suppression must be a mapping")
        rules.append(
            SuppressionRule(
                rule=str(entry.get("rule", "*")),
                paths=_as_tuple(entry.get("paths"), ("*",)),
                tools=_as_tuple(entry.get("tools"), ("*",)),
                fingerprint=(
                    str(entry["fingerprint"]) if entry.get("fingerprint") is not None else None
                ),
                reason=str(entry.get("reason", "")),
                expires=_as_date(entry.get("expires")),
                source=str(source),
            )
        )
    return rules


def _load_document(path: Path) -> dict[str, Any]:
    """Read and parse one policy file."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SuppressionPolicyError(f"Cannot read suppression policy '{path}': {exc}") from exc
    try:
        document = yaml.safe_load(raw) or {}
    except yaml.YAMLError as exc:
        raise SuppressionPolicyError(f"'{path}' is not valid YAML: {exc}") from exc
    if not isinstance(document, dict):
        raise SuppressionPolicyError(f"'{path}': policy must be a mapping")
    return document


def load_policy(path: Path, _loaded: set[Path] | None = None, _depth: int = 0) -> SuppressionPolicy:
    """Load a policy and everything it extends.

    Parents are resolved relative to the file that names them, so a shared baseline can sit
    outside the repository being scanned.

    The set of already-loaded files is shared across sibling branches, not threaded down
    each one separately. Two policies extending a common baseline is ordinary, and a
    per-branch record would load that baseline once per branch and duplicate every rule in
    it -- double-counting expiries and misreporting which files a policy came from.

    Rules from the extending file are matched *before* inherited ones, so a repository can
    override a baseline suppression rather than only add to it.
    """
    if _depth > CONST_SUPPRESSION_MAX_INHERITANCE_DEPTH:
        raise SuppressionPolicyError(
            f"Suppression policy inheritance exceeded "
            f"{CONST_SUPPRESSION_MAX_INHERITANCE_DEPTH} levels at '{path}'"
        )

    resolved = path.resolve()
    loaded = _loaded if _loaded is not None else set()
    loaded.add(resolved)

    document = _load_document(resolved)
    policy = SuppressionPolicy(rules=_parse_rules(document, resolved), sources=[str(resolved)])

    for parent in _as_tuple(document.get("extends"), ()):
        parent_path = (resolved.parent / parent).resolve()
        if parent_path in loaded:
            logger.debug("Skipping already-loaded suppression policy '%s'.", parent_path)
            continue
        inherited = load_policy(parent_path, loaded, _depth + 1)
        policy.rules.extend(inherited.rules)
        policy.sources.extend(inherited.sources)

    return policy


def empty_policy() -> SuppressionPolicy:
    """Return a policy that suppresses nothing."""
    return SuppressionPolicy()


__all__ = [
    "SuppressionPolicy",
    "SuppressionPolicyError",
    "SuppressionRule",
    "empty_policy",
    "load_policy",
]
