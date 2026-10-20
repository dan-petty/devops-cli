"""Deterministic finding-group model analysis, G10 verification, and report rendering (#1147).

Groups admitted tool and advisory findings deterministically into one model job per group:
- `(path, enclosing_symbol)` for code regions
- `(manifest, object)` for Kubernetes manifests
- `(lockfile, purl)` for package advisories

Every model output is validated against G10 checks before inclusion in `analysis.json` and the
`## Model Analysis (Model-Written)` section of `review.md`. `findings.json` and `findings.sarif`
never contain model-written analysis.
"""

from __future__ import annotations

import ast
import json
import os
import re
import shutil
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, StrictStr
from pydantic import ValidationError as PydanticValidationError

from devops_cli.ai.review.pool import ReviewWorkerPool
from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.constants import (
    CONST_ANALYSIS_ADVISORY_TOOLS,
    CONST_ANALYSIS_DROP_REASON_BUDGET,
    CONST_ANALYSIS_DROP_REASON_UNAVAILABLE,
    CONST_ANALYSIS_K8S_TOOLS,
    CONST_ANALYSIS_PROMPT_FILENAME,
    CONST_ANALYSIS_REJECTION_MODEL_CALL_ERROR,
    CONST_ANALYSIS_REJECTION_REPLY_TRUNCATED,
    CONST_ANALYSIS_REJECTION_SCHEMA_VALIDATION_FAILED,
    CONST_FINISH_REASON_LENGTH,
    CONST_REVIEW_ANALYSIS_FILENAME,
)
from devops_cli.config.defaults import (
    DEFAULT_AI_TEMPERATURE,
    DEFAULT_AI_TOP_P,
    DEFAULT_ANALYSIS_ANCHOR_CONTEXT_LINES,
    DEFAULT_ANALYSIS_PYTHON_FLOOR,
    DEFAULT_ANALYSIS_REFERENCE_BUDGET_CHARS,
    DEFAULT_ANALYSIS_SAMPLING_SEED,
    DEFAULT_GATEWAY_REVIEW_CONCURRENCY,
    DEFAULT_LOCAL_BIN_DIR,
)
from devops_cli.core.process import run_subprocess
from devops_cli.core.serialization import extract_json_block
from devops_cli.review.anchors import AdvisoryAnchor
from devops_cli.review.finding import Finding
from devops_cli.review.fingerprint import extract_enclosing_symbol
from devops_cli.review.rules_pack import discover_pack_rules
from devops_cli.review.state import FindingState
from devops_cli.security.sanitizer import mask_secrets
from devops_cli.tools_lock import load_tools_lock

GroupKind = Literal["region", "kubernetes", "advisory"]
RelationKind = Literal["caller", "callee", "same-symbol", "same-rule"]

_PYTHON_FENCE_RE: Final[re.Pattern[str]] = re.compile(
    r"```(?:python|py)\s*\n(.*?)```",
    re.DOTALL | re.IGNORECASE,
)
_VERSION_TOKEN_RE: Final[re.Pattern[str]] = re.compile(
    r"\bv?(\d+\.\d+(?:\.\d+)*(?:[a-zA-Z0-9._-]*)?)\b"
)
_PKG_SPEC_RE: Final[re.Pattern[str]] = re.compile(
    r"\b([a-zA-Z0-9_.-]+)\s*(?:==|>=|<=|~=|@)\s*v?(\d+\.\d+(?:\.\d+)*)\b"
)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FindingGroup(_StrictModel):
    """A deterministic group of admitted findings sharing one code region, K8s object, or purl."""

    group_id: str
    kind: GroupKind
    key: tuple[str, str]
    findings: tuple[Finding, ...]

    @property
    def finding_ids(self) -> tuple[str, ...]:
        """Ordered fingerprint IDs of the group's findings."""
        return tuple(f.fingerprint_v2 for f in self.findings)


class AnchorExcerpt(_StrictModel):
    """Secret-masked source excerpt around a finding's anchor region."""

    path: str
    start_line: int
    end_line: int
    excerpt: str


class SymbolNeighbour(_StrictModel):
    """A symbol-graph or rule neighbour provided to a group analysis job."""

    target: str
    relation: RelationKind


class EnvironmentFacts(_StrictModel):
    """Language floor, runtime pin, tool versions, and locked package versions for G10 checks."""

    language_floor: str = DEFAULT_ANALYSIS_PYTHON_FLOOR
    python_pin: str = ""
    tool_versions: dict[str, str] = Field(default_factory=dict)
    locked_packages: dict[str, list[str]] = Field(default_factory=dict)
    advisory_fixed_versions: dict[str, list[str]] = Field(default_factory=dict)


class AnalysisJobInput(_StrictModel):
    """Complete, reproducible input payload for one finding-group model job."""

    group_id: str
    kind: GroupKind
    key: tuple[str, str]
    finding_ids: list[str]
    finding_summaries: list[dict[str, str]]
    anchor_regions: list[AnchorExcerpt]
    neighbours: list[SymbolNeighbour]
    references: dict[str, str]
    needed_keys: list[str]
    received_keys: list[str]
    dropped_keys: dict[str, str]
    reference_coverage: float
    environment: EnvironmentFacts


class RelatedItem(_StrictModel):
    """A related finding ID or symbol-graph neighbour cited by the model."""

    target: StrictStr
    relation: RelationKind
    detail: StrictStr = ""


class PlanStep(_StrictModel):
    """A remediation step citing one or more admitted finding IDs."""

    description: StrictStr
    finding_ids: list[StrictStr]


class DocQuote(_StrictModel):
    """An exact quote from a provided reference document key."""

    key: StrictStr
    text: StrictStr


class GroupAnalysisOutput(_StrictModel):
    """Validated model output for a finding group (no diff, state, severity, or location fields)."""

    explanation: StrictStr
    root_cause: StrictStr
    related_items: list[RelatedItem] = Field(default_factory=list)
    plan_steps: list[PlanStep] = Field(default_factory=list)
    doc_quotes: list[DocQuote] = Field(default_factory=list)
    code_quotes: list[StrictStr] = Field(default_factory=list)
    suppression_note: StrictStr | None = None


class SamplingRecord(_StrictModel):
    """Recorded sampling configuration for reproducible group analysis (#1070)."""

    temperature: float = DEFAULT_AI_TEMPERATURE
    top_p: float = DEFAULT_AI_TOP_P
    seed: int = DEFAULT_ANALYSIS_SAMPLING_SEED


class RatioRecord(_StrictModel):
    """Numerator and denominator for reference coverage aggregation."""

    numerator: int = 0
    denominator: int = 0
    reason: str | None = None


class GroupAnalysisRecord(_StrictModel):
    """Saved record for one group job in `analysis.json`."""

    group_id: str
    kind: GroupKind
    key: tuple[str, str]
    finding_ids: list[str]
    needed_keys: list[str]
    received_keys: list[str]
    dropped_keys: dict[str, str]
    reference_coverage: float
    sampling: SamplingRecord
    status: Literal["verified", "rejected", "skipped"]
    output: GroupAnalysisOutput | None = None
    rejected_reasons: list[str] = Field(default_factory=list)


class AnalysisReport(_StrictModel):
    """Top-level `analysis.json` payload for a review session."""

    groups: list[GroupAnalysisRecord]
    sampling: SamplingRecord
    reference_coverage: RatioRecord
    rejections: dict[str, int]
    model_calls: int
    max_concurrency: int = DEFAULT_GATEWAY_REVIEW_CONCURRENCY


def _is_k8s_finding(finding: Finding) -> bool:
    if finding.tool.lower() in CONST_ANALYSIS_K8S_TOOLS:
        return True
    loc = finding.logical_location or ""
    return finding.path.endswith((".yaml", ".yml")) and "/" in loc and not loc.startswith("pkg:")


def _resolve_region_symbol(finding: Finding, content: str | None) -> str:
    if finding.symbol and finding.symbol.strip():
        return finding.symbol.strip()
    if content and finding.line is not None:
        return extract_enclosing_symbol(content, finding.line)
    return "<module>"


def _classify_finding_group(
    finding: Finding,
    file_contents: Mapping[str, str],
) -> tuple[GroupKind, tuple[str, str]]:
    if (
        isinstance(finding.anchor, AdvisoryAnchor)
        or finding.tool.lower() in CONST_ANALYSIS_ADVISORY_TOOLS
    ):
        purl = (
            finding.anchor.purl
            if isinstance(finding.anchor, AdvisoryAnchor)
            else (finding.logical_location or finding.rule_id)
        )
        return "advisory", (finding.path, purl)
    if _is_k8s_finding(finding):
        obj = finding.logical_location or finding.symbol or "<manifest>"
        return "kubernetes", (finding.path, obj)
    symbol = _resolve_region_symbol(finding, file_contents.get(finding.path))
    return "region", (finding.path, symbol)


def group_findings_for_analysis(
    findings: Sequence[Finding],
    file_contents: Mapping[str, str] | None = None,
) -> list[FindingGroup]:
    """Deterministically group non-suppressed admitted findings into one job per group."""
    contents = file_contents or {}
    buckets: dict[tuple[GroupKind, tuple[str, str]], list[Finding]] = {}
    for finding in findings:
        if finding.state == FindingState.SUPPRESSED:
            continue
        group_key = _classify_finding_group(finding, contents)
        buckets.setdefault(group_key, []).append(finding)

    groups: list[FindingGroup] = []
    for kind, key in sorted(buckets):
        ordered = sorted(
            buckets[(kind, key)],
            key=lambda f: (f.line or 0, f.tool, f.rule_id, f.fingerprint_v2),
        )
        groups.append(
            FindingGroup(
                group_id=f"{kind}:{key[0]}:{key[1]}",
                kind=kind,
                key=key,
                findings=tuple(ordered),
            )
        )
    return groups


def _build_anchor_excerpt(
    finding: Finding,
    content: str | None,
    context_lines: int,
) -> AnchorExcerpt | None:
    if not content:
        return None
    lines = content.splitlines()
    if not lines:
        return None
    line_no = finding.line or 1
    end_no = finding.end_line or line_no
    start_idx = max(1, line_no - context_lines)
    end_idx = min(len(lines), end_no + context_lines)
    raw_slice = "\n".join(lines[start_idx - 1 : end_idx])
    return AnchorExcerpt(
        path=finding.path,
        start_line=start_idx,
        end_line=end_idx,
        excerpt=mask_secrets(raw_slice),
    )


def _collect_anchor_excerpts(
    group: FindingGroup,
    file_contents: Mapping[str, str],
    context_lines: int,
) -> list[AnchorExcerpt]:
    seen: set[tuple[str, int, int]] = set()
    excerpts: list[AnchorExcerpt] = []
    for finding in group.findings:
        excerpt = _build_anchor_excerpt(finding, file_contents.get(finding.path), context_lines)
        if excerpt is not None and (excerpt.path, excerpt.start_line, excerpt.end_line) not in seen:
            seen.add((excerpt.path, excerpt.start_line, excerpt.end_line))
            excerpts.append(excerpt)
    return excerpts


def _pack_rule_doc_text(rule_id: str) -> str | None:
    pack = discover_pack_rules()
    if rule_id not in pack:
        return None
    rule_path, _ = pack[rule_id]
    try:
        parsed = yaml.safe_load(rule_path.read_text(encoding="utf-8"))
        rules = parsed.get("rules") if isinstance(parsed, dict) else None
        if isinstance(rules, list) and rules and isinstance(rules[0], dict):
            msg = str(rules[0].get("message", "")).strip()
            return f"{rule_id}: {msg}" if msg else rule_id
    except OSError, yaml.YAMLError:
        return None
    return None


def _resolve_rule_doc(
    finding: Finding,
    key: str,
    rule_docs: Mapping[str, str],
) -> str | None:
    for candidate in (key, f"{finding.tool}:{finding.rule_id}", finding.rule_id):
        if candidate in rule_docs:
            return rule_docs[candidate]
    if pack_text := _pack_rule_doc_text(finding.rule_id):
        return pack_text
    parts = [p for p in (finding.description, finding.message, finding.fix) if p]
    return "\n".join(dict.fromkeys(parts)) if parts else None


def _collect_reference_candidates(
    group: FindingGroup,
    rule_docs: Mapping[str, str],
    kb_manuals: Mapping[str, str],
    tool_versions: Mapping[str, str],
) -> list[tuple[str, str | None]]:
    candidates: list[tuple[str, str | None]] = []
    seen: set[str] = set()
    for finding in group.findings:
        ver = finding.tool_version or tool_versions.get(finding.tool.lower(), "installed")
        key = f"rule:{finding.tool.lower()}:{finding.rule_id}@{ver}"
        if key not in seen:
            seen.add(key)
            candidates.append((key, _resolve_rule_doc(finding, key, rule_docs)))
    for kb_key in sorted(kb_manuals):
        norm_key = kb_key if kb_key.startswith("kb:") else f"kb:{kb_key}"
        if norm_key not in seen:
            seen.add(norm_key)
            candidates.append((norm_key, kb_manuals[kb_key]))
    return candidates


def _apply_reference_budget(
    candidates: Sequence[tuple[str, str | None]],
    budget_chars: int,
) -> tuple[dict[str, str], list[str], list[str], dict[str, str], float]:
    needed_keys = [key for key, _ in candidates]
    received_keys: list[str] = []
    dropped_keys: dict[str, str] = {}
    references: dict[str, str] = {}
    used_chars = 0

    for key, text in candidates:
        if not text:
            dropped_keys[key] = CONST_ANALYSIS_DROP_REASON_UNAVAILABLE
            continue
        if used_chars + len(text) > budget_chars:
            dropped_keys[key] = CONST_ANALYSIS_DROP_REASON_BUDGET
            continue
        references[key] = text
        received_keys.append(key)
        used_chars += len(text)

    coverage = len(received_keys) / len(needed_keys) if needed_keys else 1.0
    return references, needed_keys, received_keys, dropped_keys, coverage


def default_environment_facts(findings: Sequence[Finding] = ()) -> EnvironmentFacts:
    """Build default EnvironmentFacts from `tools.lock` and finding metadata."""
    try:
        lock = load_tools_lock()
        python_pin = lock.python_version
        tool_versions = {name.lower(): tool.version for name, tool in lock.tools().items()}
    except OSError, ValueError:
        python_pin = "3.14"
        tool_versions = {}

    locked_packages: dict[str, list[str]] = {}
    advisory_fixed: dict[str, list[str]] = {}
    for finding in findings:
        if finding.tool_version:
            tool_versions.setdefault(finding.tool.lower(), finding.tool_version)
        if isinstance(finding.anchor, AdvisoryAnchor):
            locked_packages.setdefault(finding.anchor.purl, []).append(
                finding.anchor.locked_version
            )
        fixed = finding.properties.get("fixed_versions")
        if isinstance(fixed, list) and fixed:
            advisory_fixed[finding.rule_id] = [str(v) for v in fixed]

    return EnvironmentFacts(
        language_floor=DEFAULT_ANALYSIS_PYTHON_FLOOR,
        python_pin=python_pin,
        tool_versions=tool_versions,
        locked_packages=locked_packages,
        advisory_fixed_versions=advisory_fixed,
    )


def build_analysis_job_input(
    group: FindingGroup,
    *,
    file_contents: Mapping[str, str] | None = None,
    rule_docs: Mapping[str, str] | None = None,
    kb_manuals: Mapping[str, str] | None = None,
    neighbours: Sequence[SymbolNeighbour] | None = None,
    environment: EnvironmentFacts | None = None,
    context_lines: int = DEFAULT_ANALYSIS_ANCHOR_CONTEXT_LINES,
    reference_budget_chars: int = DEFAULT_ANALYSIS_REFERENCE_BUDGET_CHARS,
) -> AnalysisJobInput:
    """Construct an `AnalysisJobInput` with secret-masked excerpts and reference budget tracking."""
    contents = file_contents or {}
    env = environment or default_environment_facts(group.findings)
    candidates = _collect_reference_candidates(
        group,
        rule_docs or {},
        kb_manuals or {},
        env.tool_versions,
    )
    references, needed_keys, received_keys, dropped_keys, coverage = _apply_reference_budget(
        candidates,
        reference_budget_chars,
    )
    summaries = [
        {
            "id": f.fingerprint_v2,
            "tool": f.tool,
            "rule_id": f.rule_id,
            "location": f.location_display,
            "message": mask_secrets(f.message),
        }
        for f in group.findings
    ]
    return AnalysisJobInput(
        group_id=group.group_id,
        kind=group.kind,
        key=group.key,
        finding_ids=list(group.finding_ids),
        finding_summaries=summaries,
        anchor_regions=_collect_anchor_excerpts(group, contents, context_lines),
        neighbours=list(neighbours or ()),
        references=references,
        needed_keys=needed_keys,
        received_keys=received_keys,
        dropped_keys=dropped_keys,
        reference_coverage=coverage,
        environment=env,
    )


def _check_finding_ids(output: GroupAnalysisOutput, admitted_ids: set[str]) -> bool:
    cited = [fid for step in output.plan_steps for fid in step.finding_ids]
    return bool(cited) and all(fid in admitted_ids for fid in cited)


def _check_related_targets(
    output: GroupAnalysisOutput,
    admitted_ids: set[str],
    neighbours: Sequence[SymbolNeighbour],
) -> bool:
    allowed_neighbours = {(n.target, n.relation) for n in neighbours}
    neighbour_targets = {n.target for n in neighbours}
    for item in output.related_items:
        if item.target in admitted_ids:
            continue
        if item.target in neighbour_targets and (item.target, item.relation) in allowed_neighbours:
            continue
        return False
    return True


def _quote_matches_content(quote: str, content: str) -> bool:
    clean_quote = quote.rstrip("\r\n")
    if not clean_quote:
        return False
    content_lines = content.splitlines()
    quote_lines = clean_quote.splitlines()
    window = len(quote_lines)
    if window == 1:
        return quote_lines[0] in content_lines
    return any(
        content_lines[idx : idx + window] == quote_lines
        for idx in range(len(content_lines) - window + 1)
    )


def _check_code_quotes(output: GroupAnalysisOutput, file_contents: Mapping[str, str]) -> bool:
    if not output.code_quotes:
        return True
    return all(
        any(_quote_matches_content(quote, content) for content in file_contents.values())
        for quote in output.code_quotes
    )


def _check_doc_quotes(output: GroupAnalysisOutput, job_input: AnalysisJobInput) -> bool:
    received = set(job_input.received_keys)
    for dq in output.doc_quotes:
        if dq.key not in received or not dq.text:
            return False
        if dq.text not in job_input.references.get(dq.key, ""):
            return False
    return True


def _allowed_versions_and_names(env: EnvironmentFacts) -> tuple[set[str], set[str]]:
    versions: set[str] = set()
    names: set[str] = {"python"}
    if env.python_pin:
        versions.add(env.python_pin.lstrip("v"))
    for match in _VERSION_TOKEN_RE.findall(env.language_floor):
        versions.add(match.lstrip("v"))
    if env.language_floor.startswith("py") and env.language_floor[2:].isdigit():
        digits = env.language_floor[2:]
        versions.add(f"{digits[0]}.{digits[1:]}")
    for tool, ver in env.tool_versions.items():
        names.add(tool.lower().replace("_", "-"))
        versions.add(ver.lstrip("v"))
    for pkg, pkg_versions in env.locked_packages.items():
        names.add(pkg.lower().replace("_", "-"))
        if "@" in pkg:
            versions.add(pkg.rsplit("@", 1)[-1].lstrip("v"))
        versions.update(v.lstrip("v") for v in pkg_versions)
    for pkg, fixed_versions in env.advisory_fixed_versions.items():
        names.add(pkg.lower().replace("_", "-"))
        versions.update(v.lstrip("v") for v in fixed_versions)
    return versions, names


def _check_versions_and_packages(output: GroupAnalysisOutput, env: EnvironmentFacts) -> bool:
    allowed_versions, allowed_names = _allowed_versions_and_names(env)
    texts = [
        output.explanation,
        output.root_cause,
        *(step.description for step in output.plan_steps),
        output.suppression_note or "",
    ]
    combined = "\n".join(texts)
    prose = _PYTHON_FENCE_RE.sub("", combined)
    for pkg_name, ver in _PKG_SPEC_RE.findall(prose):
        norm_name = pkg_name.lower().replace("_", "-")
        if norm_name not in allowed_names or ver.lstrip("v") not in allowed_versions:
            return False
    return all(ver.lstrip("v") in allowed_versions for ver in _VERSION_TOKEN_RE.findall(prose))


def _default_ruff_block_checker(code: str, language_floor: str) -> list[str]:
    search_path = os.pathsep.join((str(DEFAULT_LOCAL_BIN_DIR), os.environ.get("PATH", "")))
    ruff_bin = shutil.which("ruff", path=search_path) or "ruff"
    floor = language_floor if language_floor.startswith("py") else DEFAULT_ANALYSIS_PYTHON_FLOOR
    res = run_subprocess(
        [
            ruff_bin,
            "check",
            "--target-version",
            floor,
            "--select",
            "F,UP",
            "--isolated",
            "--no-cache",
            "--stdin-filename",
            "snippet.py",
            "-",
        ],
        input=code,
        check=False,
        capture_output=True,
        timeout=10,
    )
    if res.returncode == 0:
        return []
    return [line for line in (res.stdout or res.stderr).splitlines() if line.strip()]


def _extract_python_blocks(output: GroupAnalysisOutput) -> list[str]:
    texts = [
        output.explanation,
        output.root_cause,
        *(step.description for step in output.plan_steps),
        output.suppression_note or "",
    ]
    return [match.group(1) for text in texts for match in _PYTHON_FENCE_RE.finditer(text)]


def _check_python_code_blocks(
    output: GroupAnalysisOutput,
    language_floor: str,
    checker: Callable[[str, str], list[str]] | None,
) -> bool:
    blocks = _extract_python_blocks(output)
    if not blocks:
        return True
    active_checker = checker or _default_ruff_block_checker
    for block in blocks:
        try:
            ast.parse(block)
        except SyntaxError:
            return False
        if active_checker(block, language_floor):
            return False
    return True


def verify_group_analysis(
    output: GroupAnalysisOutput,
    job_input: AnalysisJobInput,
    *,
    admitted_finding_ids: set[str] | None = None,
    file_contents: Mapping[str, str] | None = None,
    rejection_counts: dict[str, int] | None = None,
    python_block_checker: Callable[[str, str], list[str]] | None = None,
) -> tuple[GroupAnalysisOutput | None, list[str]]:
    """Run all G10 checks on a `GroupAnalysisOutput`, recording and dropping any failures."""
    admitted = admitted_finding_ids or set(job_input.finding_ids)
    contents = file_contents or {}
    checks: tuple[tuple[str, bool], ...] = (
        ("unknown-finding-id", _check_finding_ids(output, admitted)),
        ("invalid-related-target", _check_related_targets(output, admitted, job_input.neighbours)),
        ("unmatched-code-quote", _check_code_quotes(output, contents)),
        ("unmatched-doc-quote", _check_doc_quotes(output, job_input)),
        (
            "unverified-version-or-package",
            _check_versions_and_packages(output, job_input.environment),
        ),
        (
            "invalid-python-code-block",
            _check_python_code_blocks(
                output,
                job_input.environment.language_floor,
                python_block_checker,
            ),
        ),
    )
    reasons = [reason for reason, ok in checks if not ok]
    if rejection_counts is not None:
        for reason in reasons:
            rejection_counts[reason] = rejection_counts.get(reason, 0) + 1
    return (None if reasons else output), reasons


def _parse_model_group_output(raw_reply: Any) -> GroupAnalysisOutput | None:
    if isinstance(raw_reply, GroupAnalysisOutput):
        return raw_reply
    text = (
        raw_reply if isinstance(raw_reply, str) else str(getattr(raw_reply, "content", raw_reply))
    )
    extracted = extract_json_block(text, default=None)
    candidate = extracted if isinstance(extracted, dict) else None
    if candidate is None:
        try:
            parsed = json.loads(text)
            candidate = parsed if isinstance(parsed, dict) else None
        except ValueError:
            return None
    if candidate is None:
        return None
    try:
        return GroupAnalysisOutput.model_validate(candidate)
    except PydanticValidationError:
        return None


def _rejected_group_record(
    job_input: AnalysisJobInput,
    sampling: SamplingRecord,
    reason: str,
) -> GroupAnalysisRecord:
    return GroupAnalysisRecord(
        group_id=job_input.group_id,
        kind=job_input.kind,
        key=job_input.key,
        finding_ids=job_input.finding_ids,
        needed_keys=job_input.needed_keys,
        received_keys=job_input.received_keys,
        dropped_keys=job_input.dropped_keys,
        reference_coverage=job_input.reference_coverage,
        sampling=sampling,
        status="rejected",
        output=None,
        rejected_reasons=[reason],
    )


def _execute_single_group_job(
    job_input: AnalysisJobInput,
    *,
    llm_client: Any,
    system_prompt: str,
    sampling: SamplingRecord,
    admitted_ids: set[str],
    file_contents: Mapping[str, str],
    python_block_checker: Callable[[str, str], list[str]] | None,
) -> tuple[GroupAnalysisRecord, list[str]]:
    user_prompt = job_input.model_dump_json(indent=2)
    raw = llm_client.chat(
        system_prompt,
        user_prompt,
        temperature=sampling.temperature,
        top_p=sampling.top_p,
        seed=sampling.seed,
    )
    if getattr(raw, "finish_reason", None) == CONST_FINISH_REASON_LENGTH:
        reason = CONST_ANALYSIS_REJECTION_REPLY_TRUNCATED
        return (_rejected_group_record(job_input, sampling, reason), [reason])
    parsed = _parse_model_group_output(raw)
    if parsed is None:
        reason = CONST_ANALYSIS_REJECTION_SCHEMA_VALIDATION_FAILED
        return (_rejected_group_record(job_input, sampling, reason), [reason])
    verified, reasons = verify_group_analysis(
        parsed,
        job_input,
        admitted_finding_ids=admitted_ids,
        file_contents=file_contents,
        python_block_checker=python_block_checker,
    )
    return (
        GroupAnalysisRecord(
            group_id=job_input.group_id,
            kind=job_input.kind,
            key=job_input.key,
            finding_ids=job_input.finding_ids,
            needed_keys=job_input.needed_keys,
            received_keys=job_input.received_keys,
            dropped_keys=job_input.dropped_keys,
            reference_coverage=job_input.reference_coverage,
            sampling=sampling,
            status="verified" if verified is not None else "rejected",
            output=verified,
            rejected_reasons=reasons,
        ),
        reasons,
    )


def run_group_analysis(
    findings: Sequence[Finding],
    *,
    llm_client: Any | None,
    file_contents: Mapping[str, str] | None = None,
    rule_docs: Mapping[str, str] | None = None,
    kb_manuals: Mapping[str, str] | None = None,
    neighbours_by_group: Mapping[str, Sequence[SymbolNeighbour]] | None = None,
    environment: EnvironmentFacts | None = None,
    sampling: SamplingRecord | None = None,
    session_dir: Path | None = None,
    concurrency: int | None = None,
    python_block_checker: Callable[[str, str], list[str]] | None = None,
) -> AnalysisReport:
    """Group admitted findings, dispatch one model job per group via ReviewWorkerPool, and save `analysis.json`."""
    contents = file_contents or {}
    groups = group_findings_for_analysis(findings, file_contents=contents)
    eff_sampling = sampling or SamplingRecord()
    eff_env = environment or default_environment_facts(findings)
    admitted_ids = {f.fingerprint_v2 for f in findings if f.state != FindingState.SUPPRESSED}
    capped_concurrency = min(
        max(1, int(concurrency or DEFAULT_GATEWAY_REVIEW_CONCURRENCY)),
        DEFAULT_GATEWAY_REVIEW_CONCURRENCY,
    )

    jobs = [
        build_analysis_job_input(
            group,
            file_contents=contents,
            rule_docs=rule_docs,
            kb_manuals=kb_manuals,
            neighbours=(neighbours_by_group or {}).get(group.group_id),
            environment=eff_env,
        )
        for group in groups
    ]

    records: list[GroupAnalysisRecord] = []
    rejections: dict[str, int] = {}
    model_calls = 0

    if llm_client is not None and jobs:
        system_prompt = load_task_prompt(CONST_ANALYSIS_PROMPT_FILENAME)
        pool = ReviewWorkerPool.create(concurrency=capped_concurrency)
        outcomes = pool.run_sync_all(
            lambda job: _execute_single_group_job(
                job,
                llm_client=llm_client,
                system_prompt=system_prompt,
                sampling=eff_sampling,
                admitted_ids=admitted_ids,
                file_contents=contents,
                python_block_checker=python_block_checker,
            ),
            jobs,
            return_exceptions=True,
        )
        model_calls = len(jobs)
        for job, outcome in zip(jobs, outcomes, strict=True):
            if isinstance(outcome, BaseException):
                err_reason = CONST_ANALYSIS_REJECTION_MODEL_CALL_ERROR
                rejections[err_reason] = rejections.get(err_reason, 0) + 1
                records.append(_rejected_group_record(job, eff_sampling, err_reason))
                continue
            rec, reasons = outcome
            records.append(rec)
            for reason in reasons:
                rejections[reason] = rejections.get(reason, 0) + 1
    else:
        records = [
            GroupAnalysisRecord(
                group_id=job.group_id,
                kind=job.kind,
                key=job.key,
                finding_ids=job.finding_ids,
                needed_keys=job.needed_keys,
                received_keys=job.received_keys,
                dropped_keys=job.dropped_keys,
                reference_coverage=job.reference_coverage,
                sampling=eff_sampling,
                status="skipped",
                output=None,
            )
            for job in jobs
        ]

    total_received = sum(len(j.received_keys) for j in jobs)
    total_needed = sum(len(j.needed_keys) for j in jobs)
    report = AnalysisReport(
        groups=records,
        sampling=eff_sampling,
        reference_coverage=RatioRecord(numerator=total_received, denominator=total_needed),
        rejections=rejections,
        model_calls=model_calls,
        max_concurrency=capped_concurrency,
    )
    if session_dir is not None:
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / CONST_REVIEW_ANALYSIS_FILENAME).write_text(
            report.model_dump_json(indent=2),
            encoding="utf-8",
        )
    return report


def _render_group_record_markdown(record: GroupAnalysisRecord) -> list[str]:
    lines = [
        f"### Group `{record.group_id}` ({record.kind})",
        f"- **Findings**: {', '.join(f'`{fid}`' for fid in record.finding_ids)}",
        f"- **Reference Coverage**: {len(record.received_keys)}/{len(record.needed_keys)} ({record.reference_coverage:.0%})",
    ]
    if record.dropped_keys:
        dropped_str = ", ".join(
            f"`{key}` ({reason})" for key, reason in sorted(record.dropped_keys.items())
        )
        lines.append(f"- **Dropped References**: {dropped_str}")
    if record.output is not None:
        out = record.output
        lines.append(f"- **Explanation**: {out.explanation}")
        lines.append(f"- **Root Cause**: {out.root_cause}")
        if out.plan_steps:
            lines.append("- **Remediation Plan**:")
            for step in out.plan_steps:
                cited = ", ".join(f"`{fid}`" for fid in step.finding_ids)
                lines.append(f"  - {step.description} ({cited})")
        if out.related_items:
            rel_str = ", ".join(f"`{r.target}` ({r.relation})" for r in out.related_items)
            lines.append(f"- **Related Items**: {rel_str}")
        if out.doc_quotes:
            lines.append("- **Rule Documentation Quotes**:")
            for dq in out.doc_quotes:
                lines.append(f'  - `{dq.key}`: "{dq.text}"')
        if out.suppression_note:
            lines.append(f"- **Suppression Note (text only)**: {out.suppression_note}")
    elif record.rejected_reasons:
        lines.append(f"- **G10 Rejected**: {', '.join(record.rejected_reasons)}")
    lines.append("")
    return lines


def render_model_analysis_markdown(report: AnalysisReport | None) -> list[str]:
    """Render the `## Model Analysis (Model-Written)` section for `review.md`."""
    if report is None or not report.groups:
        return []
    cov = report.reference_coverage
    cov_pct = (cov.numerator / cov.denominator) if cov.denominator else 1.0
    lines = [
        "## Model Analysis (Model-Written)",
        "*This section is model-written and kept strictly separate from tool-verified findings.*",
        "",
        f"- **Model Calls**: {report.model_calls} (groups: {len(report.groups)})",
        f"- **Reference Coverage**: {cov.numerator}/{cov.denominator} ({cov_pct:.0%})",
        f"- **Sampling**: temperature={report.sampling.temperature}, top_p={report.sampling.top_p}, seed={report.sampling.seed}",
    ]
    if report.rejections:
        rej_summary = ", ".join(f"`{k}`: {v}" for k, v in sorted(report.rejections.items()))
        lines.append(f"- **G10 Rejections**: {rej_summary}")
    lines.append("")
    for record in report.groups:
        lines.extend(_render_group_record_markdown(record))
    return lines


__all__ = [
    "AnalysisJobInput",
    "AnalysisReport",
    "AnchorExcerpt",
    "DocQuote",
    "EnvironmentFacts",
    "FindingGroup",
    "GroupAnalysisOutput",
    "GroupAnalysisRecord",
    "GroupKind",
    "PlanStep",
    "RatioRecord",
    "RelatedItem",
    "RelationKind",
    "SamplingRecord",
    "SymbolNeighbour",
    "build_analysis_job_input",
    "default_environment_facts",
    "group_findings_for_analysis",
    "render_model_analysis_markdown",
    "run_group_analysis",
    "verify_group_analysis",
]
