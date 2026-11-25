"""Ordered rule-table persona lens selection and bounded telemetry (#4830)."""

from __future__ import annotations

import fnmatch
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pathspec

from devops_cli.ai.personas import Persona
from devops_cli.config.constants import (
    CONST_AI_MAX_LENS_SERIES,
    CONST_GITIGNORE_PATTERN_STYLE,
)
from devops_cli.telemetry.instruments import (
    AI_LENS_TOTAL,
    LENS_COUNTER_CALLERS,
    LENS_COUNTER_LENSES,
    LENS_COUNTER_SOURCES,
    emit,
)

if TYPE_CHECKING:
    from devops_cli.ai.review.profile import ReviewProfiler

_LENS_TOML_PATH = Path(__file__).with_name("lens.toml")


@dataclass(frozen=True)
class FindingSignal:
    """Producer identity and optional CWE identifier for a static or test finding."""

    producer: str
    cwe: str | None = None


@dataclass(frozen=True)
class LensEvidence:
    """Inputs evaluated in table order to pick an AI persona lens."""

    explicit_persona: Persona | str | None = None
    step_role: str | None = None
    findings: tuple[FindingSignal, ...] = ()
    paths: tuple[str, ...] = ()
    labels: tuple[str, ...] = ()


@dataclass(frozen=True)
class LensRule:
    """One row of `lens.toml`."""

    id: str
    matcher: str
    pattern: str
    lens: str
    requires_cwe: bool = False


@dataclass(frozen=True)
class LensChoice:
    """Selected lens (or None when unmatched), rule id, and telemetry source."""

    lens: Persona | None
    rule_id: str
    source: str


@lru_cache(maxsize=4)
def load_lens_rules(path: Path = _LENS_TOML_PATH) -> tuple[LensRule, ...]:
    """Load the ordered persona lens rules from *path*."""
    raw_rows = tomllib.loads(path.read_text(encoding="utf-8")).get("rules", ())
    rules: list[LensRule] = []
    seen_ids: set[str] = set()
    for row in raw_rows:
        rule_id = str(row["id"])
        if rule_id in seen_ids:
            raise ValueError(f"Duplicate lens rule id in {path}: {rule_id!r}")
        seen_ids.add(rule_id)
        rules.append(
            LensRule(
                id=rule_id,
                matcher=str(row["matcher"]),
                pattern=str(row["pattern"]),
                lens=str(row["lens"]),
                requires_cwe=bool(row.get("requires_cwe", False)),
            )
        )
    return tuple(rules)


@lru_cache(maxsize=16)
def _compiled_pathspec(pattern: str) -> pathspec.PathSpec[Any]:
    return pathspec.PathSpec.from_lines(CONST_GITIGNORE_PATTERN_STYLE, [pattern])


def reset_lens_caches() -> None:
    """Clear cached rule table and pathspec matchers."""
    load_lens_rules.cache_clear()
    _compiled_pathspec.cache_clear()


def _match_flag(rule: LensRule, evidence: LensEvidence) -> Persona | None:
    _ = rule
    if not evidence.explicit_persona:
        return None
    if isinstance(evidence.explicit_persona, Persona):
        return evidence.explicit_persona
    return Persona(str(evidence.explicit_persona).lower())


def _match_step_role(rule: LensRule, evidence: LensEvidence) -> Persona | None:
    if evidence.step_role and evidence.step_role.lower() == rule.pattern.lower():
        return Persona(rule.lens)
    return None


def _match_finding(rule: LensRule, evidence: LensEvidence) -> Persona | None:
    target = rule.pattern.lower()
    for finding in evidence.findings:
        if finding.producer.lower() != target:
            continue
        if rule.requires_cwe and not finding.cwe:
            continue
        return Persona(rule.lens)
    return None


def _match_path(rule: LensRule, evidence: LensEvidence) -> Persona | None:
    if not evidence.paths:
        return None
    matcher = _compiled_pathspec(rule.pattern)
    for raw_path in evidence.paths:
        norm = raw_path.replace("\\", "/").removeprefix("./")
        if matcher.match_file(norm):
            return Persona(rule.lens)
    return None


def _match_label(rule: LensRule, evidence: LensEvidence) -> Persona | None:
    target = rule.pattern.lower()
    for label in evidence.labels:
        if fnmatch.fnmatchcase(label.lower(), target):
            return Persona(rule.lens)
    return None


_MATCHERS = {
    "flag": _match_flag,
    "step_role": _match_step_role,
    "finding": _match_finding,
    "path": _match_path,
    "label": _match_label,
}


def select_lens(
    evidence: LensEvidence,
    *,
    rules: Sequence[LensRule] | None = None,
) -> LensChoice:
    """Return the first matching persona lens and rule id, or `none` when unmatched."""
    active_rules = load_lens_rules() if rules is None else rules
    for rule in active_rules:
        matcher = _MATCHERS.get(rule.matcher)
        if matcher is None:
            continue
        matched = matcher(rule, evidence)
        if matched is not None:
            source = "flag" if rule.matcher == "flag" else "rule"
            return LensChoice(lens=matched, rule_id=rule.id, source=source)
    return LensChoice(lens=None, rule_id="", source="none")


def record_lens_choice(
    choice: LensChoice,
    *,
    caller: str,
    span: Any = None,
    profiler: ReviewProfiler | None = None,
    chat_prompt_digest: str = "",
) -> None:
    """Record selected lens on telemetry span, review profile, and bounded counter."""
    from devops_cli.ai.review.profile import active_profiler

    lens_label = choice.lens.value if choice.lens is not None else "none"
    if span is not None and hasattr(span, "set_attribute"):
        span.set_attribute("ai.lens", lens_label)
        span.set_attribute("ai.lens.rule", choice.rule_id)
        if chat_prompt_digest:
            span.set_attribute("ai.chat_prompt_digest", chat_prompt_digest)

    target_profiler = profiler or active_profiler()
    if target_profiler is not None:
        target_profiler.set_lens(lens_label, choice.rule_id)

    series_product = (
        len(LENS_COUNTER_CALLERS) * len(LENS_COUNTER_LENSES) * len(LENS_COUNTER_SOURCES)
    )
    if (
        series_product <= CONST_AI_MAX_LENS_SERIES
        and caller in LENS_COUNTER_CALLERS
        and lens_label in LENS_COUNTER_LENSES
        and choice.source in LENS_COUNTER_SOURCES
    ):
        emit(
            AI_LENS_TOTAL,
            1.0,
            {"caller": caller, "lens": lens_label, "source": choice.source},
        )
