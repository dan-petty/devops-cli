"""Offline unit tests for finding-group model analysis, G10 verification, and reference coverage (#1147)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

import pytest
from pydantic import ValidationError as PydanticValidationError
from typer.testing import CliRunner

from devops_cli.ai.client.models import LLMResponse
from devops_cli.ai.review.flags import ReviewStageFlags
from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator
from devops_cli.ai.review_schema import FileReviewPayload, SavedFinding
from devops_cli.ai.run_store import (
    Mechanism,
    RegressionTolerances,
    check_regression,
    compare_runs,
    new_run,
    save_run,
    set_baseline,
)
from devops_cli.config import constants
from devops_cli.config.constants import (
    CONST_ANALYSIS_DROP_REASON_BUDGET,
    CONST_FINISH_REASON_LENGTH,
    CONST_REVIEW_ANALYSIS_FILENAME,
    CONST_REVIEW_FINDINGS_FILENAME,
    CONST_REVIEW_SARIF_FILENAME,
)
from devops_cli.config.defaults import (
    DEFAULT_ANALYSIS_SAMPLING_SEED,
    DEFAULT_GATEWAY_REVIEW_CONCURRENCY,
    DEFAULT_GATEWAY_REVIEW_SLOTS,
)
from devops_cli.main import app
from devops_cli.review.anchors import AdvisoryAnchor, ToolAnchor
from devops_cli.review.finding import Finding
from devops_cli.review.score import score_sessions
from devops_cli.review.state import FindingState

CONST_ANALYSIS_REJECTION_REPLY_TRUNCATED: Final[str] = getattr(
    constants, "CONST_ANALYSIS_REJECTION_REPLY_TRUNCATED", "reply-truncated"
)

cli = CliRunner(env={"COLUMNS": "200", "NO_COLOR": "1", "TERM": "dumb"})


def _make_region_finding(
    *,
    rule_id: str = "F401",
    path: str = "src/app.py",
    line: int = 3,
    symbol: str | None = None,
    fingerprint: str = "fp-region-1",
    state: FindingState = FindingState.OPEN,
    tool: str = "ruff",
    tool_version: str = "0.15.10",
) -> Finding:
    return Finding(
        anchor=ToolAnchor(run_id="r1", result_index=0, rule_id=rule_id),
        tool=tool,
        tool_version=tool_version,
        rule_id=rule_id,
        path=path,
        line=line,
        end_line=line,
        symbol=symbol,
        message=f"{rule_id} issue at line {line}",
        description=f"Rule {rule_id} description",
        severity="MEDIUM",
        severity_derivation="rule",
        state=state,
        fingerprint_v2=fingerprint,
    )


def _make_k8s_finding(
    *,
    rule_id: str = "no-read-only-root-fs",
    path: str = "k8s/deploy.yaml",
    logical_location: str = "Deployment/web",
    fingerprint: str = "fp-k8s-1",
) -> Finding:
    return Finding(
        anchor=ToolAnchor(run_id="r2", result_index=0, rule_id=rule_id),
        tool="kube-linter",
        tool_version="0.8.1",
        rule_id=rule_id,
        path=path,
        logical_location=logical_location,
        message="container rootfs not read-only",
        severity="MEDIUM",
        severity_derivation="rule",
        state=FindingState.OPEN,
        fingerprint_v2=fingerprint,
    )


def _make_advisory_finding(
    *,
    advisory_id: str = "GHSA-1234-5678-90ab",
    path: str = "uv.lock",
    purl: str = "pkg:pypi/httpx2@0.27.0",
    locked_version: str = "0.27.0",
    fingerprint: str = "fp-adv-1",
) -> Finding:
    return Finding(
        anchor=AdvisoryAnchor(
            db="osv",
            snapshot="2026-10-01",
            advisory_id=advisory_id,
            purl=purl,
            locked_version=locked_version,
        ),
        tool="osv",
        tool_version="1.0",
        rule_id=advisory_id,
        path=path,
        logical_location=f"{purl}@{locked_version}",
        message=f"Advisory {advisory_id}",
        fix="Upgrade to 0.28.1",
        severity="HIGH",
        severity_derivation="cvss",
        state=FindingState.OPEN,
        fingerprint_v2=fingerprint,
        properties={"fixed_versions": ["0.28.1"]},
    )


class _FakeAnalysisClient:
    """Offline fake LLM client recording calls and sampling parameters."""

    def __init__(
        self,
        responses: dict[str, dict[str, Any]] | dict[str, Any],
        *,
        finish_reasons: dict[str, str | None] | str | None = None,
    ) -> None:
        self._responses = responses
        self._finish_reasons = finish_reasons
        self.calls: list[dict[str, Any]] = []

    @property
    def backend_info(self) -> str:
        return "fake/model"

    def get_context_window(self, task: str | None = None) -> int:
        return 32768

    def _resolve_content_and_group(self, user: str) -> tuple[str, str | None]:
        if "explanation" in self._responses:
            return json.dumps(self._responses), None
        for group_id, payload in self._responses.items():
            if group_id in user:
                return json.dumps(payload), group_id
        first = next(iter(self._responses.values()))
        return json.dumps(first), None

    def _resolve_finish_reason(self, group_id: str | None) -> Any:
        if isinstance(self._finish_reasons, dict):
            if group_id and group_id in self._finish_reasons:
                return self._finish_reasons[group_id]
            return self._finish_reasons.get("default")
        return self._finish_reasons

    def chat(self, system: str, user: str, **kwargs: Any) -> LLMResponse:
        self.calls.append({"system": system, "user": user, "kwargs": kwargs})
        content, group_id = self._resolve_content_and_group(user)
        reason = self._resolve_finish_reason(group_id)
        return LLMResponse(content=content, finish_reason=reason)


def test_group_findings_for_analysis_deterministically_groups_regions_k8s_and_advisories() -> None:
    """Regions group by (path, enclosing_symbol), K8s by (manifest, object), advisories by (lockfile, purl)."""
    from devops_cli.review.analysis import group_findings_for_analysis

    py_source = "def alpha():\n    x = 1\n    y = 2\n    return x\n"
    f_reg_1 = _make_region_finding(rule_id="F841", path="src/app.py", line=2, fingerprint="fp-1")
    f_reg_2 = _make_region_finding(rule_id="F841", path="src/app.py", line=3, fingerprint="fp-2")
    f_suppressed = _make_region_finding(
        rule_id="F401",
        path="src/app.py",
        line=1,
        fingerprint="fp-supp",
        state=FindingState.SUPPRESSED,
    )
    f_k8s = _make_k8s_finding()
    f_adv = _make_advisory_finding()

    forward = group_findings_for_analysis(
        [f_reg_1, f_reg_2, f_suppressed, f_k8s, f_adv],
        file_contents={"src/app.py": py_source},
    )
    reverse = group_findings_for_analysis(
        [f_adv, f_k8s, f_suppressed, f_reg_2, f_reg_1],
        file_contents={"src/app.py": py_source},
    )

    assert (
        [(g.kind, g.key, g.finding_ids) for g in forward],
        forward == reverse,
    ) == (
        [
            ("advisory", ("uv.lock", "pkg:pypi/httpx2@0.27.0"), ("fp-adv-1",)),
            ("kubernetes", ("k8s/deploy.yaml", "Deployment/web"), ("fp-k8s-1",)),
            ("region", ("src/app.py", "alpha"), ("fp-1", "fp-2")),
        ],
        True,
    )


def test_anchor_excerpts_pass_through_mask_secrets_before_model_input() -> None:
    """Every anchor excerpt (+/- N lines) passes through mask_secrets before entering AnalysisJobInput (#1017)."""
    from devops_cli.review.analysis import (
        EnvironmentFacts,
        build_analysis_job_input,
        group_findings_for_analysis,
    )

    raw_token = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"
    source = f"def connect():\n    token = '{raw_token}'\n    return token\n"
    finding = _make_region_finding(path="src/auth.py", line=2, fingerprint="fp-sec")
    (group,) = group_findings_for_analysis([finding], file_contents={"src/auth.py": source})

    job_input = build_analysis_job_input(
        group,
        file_contents={"src/auth.py": source},
        rule_docs={"rule:ruff:F401@0.15.10": "Unused import rule documentation."},
        environment=EnvironmentFacts(language_floor="py314", python_pin="3.14"),
        context_lines=2,
    )

    excerpt_text = job_input.anchor_regions[0].excerpt
    assert (
        raw_token not in excerpt_text,
        raw_token not in job_input.model_dump_json(),
        "def connect():" in excerpt_text,
    ) == (True, True, True)


def test_reference_budget_overflow_records_dropped_keys_coverage_and_names_dropped_rule_doc() -> (
    None
):
    """When reference text exceeds budget, excess keys are dropped with reason 'budget' and named in review.md."""
    from devops_cli.review.analysis import (
        AnalysisReport,
        EnvironmentFacts,
        GroupAnalysisOutput,
        GroupAnalysisRecord,
        PlanStep,
        RatioRecord,
        SamplingRecord,
        build_analysis_job_input,
        group_findings_for_analysis,
        render_model_analysis_markdown,
    )

    f1 = _make_region_finding(rule_id="F401", path="src/app.py", line=2, fingerprint="fp-1")
    f2 = _make_region_finding(rule_id="B006", path="src/app.py", line=3, fingerprint="fp-2")
    (group,) = group_findings_for_analysis(
        [f1, f2],
        file_contents={"src/app.py": "def f(x=[]):\n    import os\n    return x\n"},
    )
    docs = {
        "rule:ruff:B006@0.15.10": "B006: Do not use mutable data structures for argument defaults."
        * 3,
        "rule:ruff:F401@0.15.10": "F401: Module imported but unused.",
    }
    job = build_analysis_job_input(
        group,
        file_contents={"src/app.py": "def f(x=[]):\n    import os\n    return x\n"},
        rule_docs=docs,
        kb_manuals={"kb:python_style.md": "Manual text that also overflows the small budget." * 3},
        environment=EnvironmentFacts(language_floor="py314", python_pin="3.14"),
        reference_budget_chars=80,
    )

    report = AnalysisReport(
        groups=[
            GroupAnalysisRecord(
                group_id=group.group_id,
                kind=group.kind,
                key=group.key,
                finding_ids=list(group.finding_ids),
                needed_keys=job.needed_keys,
                received_keys=job.received_keys,
                dropped_keys=job.dropped_keys,
                reference_coverage=job.reference_coverage,
                sampling=SamplingRecord(
                    temperature=0.1, top_p=0.95, seed=DEFAULT_ANALYSIS_SAMPLING_SEED
                ),
                status="verified",
                output=GroupAnalysisOutput(
                    explanation="Unused import and mutable default argument.",
                    root_cause="Module setup left an unused import.",
                    plan_steps=[
                        PlanStep(description="Remove unused import.", finding_ids=["fp-1"])
                    ],
                ),
            )
        ],
        sampling=SamplingRecord(temperature=0.1, top_p=0.95, seed=DEFAULT_ANALYSIS_SAMPLING_SEED),
        reference_coverage=RatioRecord(
            numerator=len(job.received_keys),
            denominator=len(job.needed_keys),
        ),
        rejections={},
        model_calls=1,
    )
    markdown = "\n".join(render_model_analysis_markdown(report))

    assert (
        job.needed_keys,
        job.received_keys,
        job.dropped_keys,
        round(job.reference_coverage, 4),
        "rule:ruff:B006@0.15.10" in markdown,
        CONST_ANALYSIS_DROP_REASON_BUDGET in markdown,
    ) == (
        ["rule:ruff:F401@0.15.10", "rule:ruff:B006@0.15.10", "kb:python_style.md"],
        ["rule:ruff:F401@0.15.10"],
        {
            "rule:ruff:B006@0.15.10": CONST_ANALYSIS_DROP_REASON_BUDGET,
            "kb:python_style.md": CONST_ANALYSIS_DROP_REASON_BUDGET,
        },
        round(1 / 3, 4),
        True,
        True,
    )


@pytest.mark.parametrize(
    "forbidden_field",
    [
        {"diff": "--- a/src/app.py\n+++ b/src/app.py"},
        {"state": "VERIFIED"},
        {"status": "VERIFIED"},
        {"severity": "HIGH"},
        {"location": "src/app.py:1"},
        {"path": "src/app.py"},
        {"line": 1},
        {"findings": []},
        {"new_finding": {"title": "invented"}},
        {"suppression_note": {"reason": "structured dict not allowed"}},
        {"related_items": [{"target": "fp-1", "relation": "invented-relation"}]},
    ],
)
def test_group_analysis_output_schema_forbids_diff_and_finding_mutation_fields(
    forbidden_field: dict[str, Any],
) -> None:
    """GroupAnalysisOutput has no diff, state, severity, location, or new_finding fields."""
    from devops_cli.review.analysis import GroupAnalysisOutput

    base_payload: dict[str, Any] = {
        "explanation": "Grounded explanation.",
        "root_cause": "Shared root cause.",
        "related_items": [{"target": "fp-1", "relation": "same-symbol"}],
        "plan_steps": [{"description": "Fix the symbol.", "finding_ids": ["fp-1"]}],
        "doc_quotes": [{"key": "rule:ruff:F401@0.15.10", "text": "unused"}],
        "code_quotes": ["import os"],
        "suppression_note": "Plain text note only; add to .devops/review.toml via PR if needed.",
    }
    valid = GroupAnalysisOutput.model_validate(base_payload)
    assert (valid.explanation, valid.suppression_note is not None) == (
        "Grounded explanation.",
        True,
    )

    with pytest.raises(PydanticValidationError):
        GroupAnalysisOutput.model_validate({**base_payload, **forbidden_field})


def test_g10_checks_drop_and_count_failures_by_reason() -> None:
    """Every G10 check drops invalid model output and increments its typed rejection reason."""
    from devops_cli.review.analysis import (
        DocQuote,
        EnvironmentFacts,
        GroupAnalysisOutput,
        PlanStep,
        RelatedItem,
        SymbolNeighbour,
        build_analysis_job_input,
        group_findings_for_analysis,
        verify_group_analysis,
    )

    source = "import os\ndef run() -> int:\n    return 1\n"
    finding = _make_region_finding(rule_id="F401", path="src/app.py", line=1, fingerprint="fp-1")
    (group,) = group_findings_for_analysis([finding], file_contents={"src/app.py": source})
    env = EnvironmentFacts(
        language_floor="py314",
        python_pin="3.14",
        tool_versions={"ruff": "0.15.10"},
        locked_packages={"pydantic": ["2.10.0"]},
        advisory_fixed_versions={"httpx2": ["0.28.1"]},
    )
    job = build_analysis_job_input(
        group,
        file_contents={"src/app.py": source},
        rule_docs={"rule:ruff:F401@0.15.10": "Module imported but unused."},
        neighbours=[SymbolNeighbour(target="src/caller.py:main", relation="caller")],
        environment=env,
    )

    def _fake_ruff_checker(code: str, floor: str) -> list[str]:
        if "Optional[" in code or "unused_var" in code:
            return ["UP045 Use `X | None` instead of `Optional[X]`"]
        return []

    valid_output = GroupAnalysisOutput(
        explanation="In Python 3.14 with ruff 0.15.10, `os` is unused:\n```python\ndef run() -> int:\n    return 1\n```",
        root_cause="Unused import left in module.",
        related_items=[RelatedItem(target="src/caller.py:main", relation="caller")],
        plan_steps=[PlanStep(description="Remove `import os`.", finding_ids=["fp-1"])],
        doc_quotes=[DocQuote(key="rule:ruff:F401@0.15.10", text="Module imported but unused.")],
        code_quotes=["import os"],
        suppression_note="If intentional re-export, document in .devops/review.toml.",
    )
    ok_counts: dict[str, int] = {}
    verified, ok_reasons = verify_group_analysis(
        valid_output,
        job,
        admitted_finding_ids={"fp-1"},
        file_contents={"src/app.py": source},
        rejection_counts=ok_counts,
        python_block_checker=_fake_ruff_checker,
    )
    assert (verified == valid_output, ok_reasons, ok_counts) == (True, [], {})

    bad_output = GroupAnalysisOutput(
        explanation="Upgrade to ruff 99.88.77:\n```python\nfrom typing import Optional\ndef bad(x: Optional[int]) -> None:\n    pass\n```",
        root_cause=" Broken syntax and unverified version.",
        related_items=[RelatedItem(target="src/invented.py:ghost", relation="caller")],
        plan_steps=[PlanStep(description="Fix ghost finding.", finding_ids=["fp-unknown"])],
        doc_quotes=[DocQuote(key="rule:ruff:F401@0.15.10", text="Invented quote not in doc.")],
        code_quotes=["import invented_module"],
    )
    rejections: dict[str, int] = {}
    rejected, reasons = verify_group_analysis(
        bad_output,
        job,
        admitted_finding_ids={"fp-1"},
        file_contents={"src/app.py": source},
        rejection_counts=rejections,
        python_block_checker=_fake_ruff_checker,
    )

    syntax_bad = valid_output.model_copy(
        update={"explanation": "Bad syntax:\n```python\ndef broken(:\n    pass\n```"}
    )
    verify_group_analysis(
        syntax_bad,
        job,
        admitted_finding_ids={"fp-1"},
        file_contents={"src/app.py": source},
        rejection_counts=rejections,
        python_block_checker=_fake_ruff_checker,
    )

    assert (
        rejected,
        set(reasons),
        rejections,
    ) == (
        None,
        {
            "unknown-finding-id",
            "invalid-related-target",
            "unmatched-code-quote",
            "unmatched-doc-quote",
            "unverified-version-or-package",
            "invalid-python-code-block",
        },
        {
            "unknown-finding-id": 1,
            "invalid-related-target": 1,
            "unmatched-code-quote": 1,
            "unmatched-doc-quote": 1,
            "unverified-version-or-package": 1,
            "invalid-python-code-block": 2,
        },
    )


def test_dispatch_runs_one_job_per_group_via_pool_capped_at_slots_and_records_sampling(
    tmp_path: Path,
) -> None:
    """Dispatch uses ReviewWorkerPool capped at DEFAULT_GATEWAY_REVIEW_CONCURRENCY and records sampling."""
    from devops_cli.review.analysis import EnvironmentFacts, run_group_analysis

    source = "def a():\n    return 1\n\ndef b():\n    return 2\n"
    f1 = _make_region_finding(rule_id="F401", path="src/app.py", line=2, fingerprint="fp-a")
    f2 = _make_region_finding(rule_id="F401", path="src/app.py", line=5, fingerprint="fp-b")
    client = _FakeAnalysisClient(
        {
            "region:src/app.py:a": {
                "explanation": "Function a issue.",
                "root_cause": "Root cause a.",
                "related_items": [],
                "plan_steps": [{"description": "Fix a.", "finding_ids": ["fp-a"]}],
                "doc_quotes": [{"key": "rule:ruff:F401@0.15.10", "text": "unused"}],
                "code_quotes": ["    return 1"],
            },
            "region:src/app.py:b": {
                "explanation": "Function b issue.",
                "root_cause": "Root cause b.",
                "related_items": [],
                "plan_steps": [{"description": "Fix b.", "finding_ids": ["fp-b"]}],
                "doc_quotes": [{"key": "rule:ruff:F401@0.15.10", "text": "unused"}],
                "code_quotes": ["    return 2"],
            },
        }
    )

    report = run_group_analysis(
        [f1, f2],
        llm_client=client,
        file_contents={"src/app.py": source},
        rule_docs={"rule:ruff:F401@0.15.10": "Module imported but unused."},
        environment=EnvironmentFacts(language_floor="py314", python_pin="3.14"),
        session_dir=tmp_path,
        concurrency=99,
        python_block_checker=lambda code, floor: [],
    )
    persisted = json.loads((tmp_path / CONST_REVIEW_ANALYSIS_FILENAME).read_text(encoding="utf-8"))

    assert (
        DEFAULT_GATEWAY_REVIEW_CONCURRENCY == sum(DEFAULT_GATEWAY_REVIEW_SLOTS.values()),
        report.max_concurrency,
        report.model_calls,
        len(client.calls),
        len(report.groups),
        report.sampling.seed,
        all("Finding Group Explanation" in c["system"] for c in client.calls),
        all(c["kwargs"].get("seed") == DEFAULT_ANALYSIS_SAMPLING_SEED for c in client.calls),
        persisted["model_calls"],
        [g["status"] for g in persisted["groups"]],
    ) == (
        True,
        DEFAULT_GATEWAY_REVIEW_CONCURRENCY,
        2,
        2,
        2,
        DEFAULT_ANALYSIS_SAMPLING_SEED,
        True,
        True,
        2,
        ["verified", "verified"],
    )


def test_findings_json_and_findings_sarif_are_byte_identical_with_group_analysis_on_and_off(
    tmp_path: Path,
) -> None:
    """findings.json and findings.sarif never contain model analysis and are byte-identical on vs off."""
    source_file = tmp_path / "src" / "app.py"
    source_file.parent.mkdir(parents=True)
    source_text = "import os\ndef main() -> int:\n    return 0\n"
    source_file.write_text(source_text, encoding="utf-8")

    admitted_finding = _make_region_finding(
        rule_id="F401", path="src/app.py", line=1, fingerprint="fp-f401"
    )
    saved_finding = SavedFinding(
        severity="MEDIUM",
        location="src/app.py:1",
        title="[ruff] F401: os imported but unused",
        description="Module imported but unused.",
        fix="Remove unused import os",
        status="VERIFIED",
        verified=True,
        verified_by="static:ruff",
        reportable=True,
        persona="devsecops",
        persona_title="Principal DevSecOps Engineer",
    )

    client = _FakeAnalysisClient(
        {
            "explanation": "Distinct model explanation marker_xyz_987.",
            "root_cause": "Unused import marker_xyz_987.",
            "related_items": [],
            "plan_steps": [{"description": "Delete import os.", "finding_ids": ["fp-f401"]}],
            "doc_quotes": [],
            "code_quotes": ["import os"],
            "suppression_note": "Add suppression to .devops/review.toml if needed.",
        }
    )

    def _run_report(name: str, *, enable_analysis: bool) -> Path:
        session_dir = tmp_path / name
        orch = ReviewPipelineOrchestrator(
            session_id="session-fixed",
            session_dir=session_dir,
            llm_client=client,
            target_dir=tmp_path,
        )
        orch.admitted_scanner_findings = [admitted_finding]
        payload = FileReviewPayload(
            file_path="src/app.py",
            findings=[saved_finding.model_copy(deep=True)],
            reportable=True,
        )
        orch.generate_consolidated_report(
            [payload],
            stage_flags=ReviewStageFlags(group_analysis=enable_analysis),
        )
        return session_dir

    dir_on = _run_report("with_analysis", enable_analysis=True)
    dir_off = _run_report("without_analysis", enable_analysis=False)

    findings_on = json.loads((dir_on / CONST_REVIEW_FINDINGS_FILENAME).read_text(encoding="utf-8"))
    findings_off = json.loads(
        (dir_off / CONST_REVIEW_FINDINGS_FILENAME).read_text(encoding="utf-8")
    )
    findings_on["generated_at"] = findings_off["generated_at"] = "2026-10-17T00:00:00+00:00"

    sarif_on = (dir_on / CONST_REVIEW_SARIF_FILENAME).read_bytes()
    sarif_off = (dir_off / CONST_REVIEW_SARIF_FILENAME).read_bytes()
    review_md_on = (dir_on / "review.md").read_text(encoding="utf-8")
    review_md_off = (dir_off / "review.md").read_text(encoding="utf-8")

    assert (
        json.dumps(findings_on, sort_keys=True) == json.dumps(findings_off, sort_keys=True),
        sarif_on == sarif_off,
        "marker_xyz_987"
        not in (dir_on / CONST_REVIEW_FINDINGS_FILENAME).read_text(encoding="utf-8"),
        b"marker_xyz_987" not in sarif_on,
        (dir_on / CONST_REVIEW_ANALYSIS_FILENAME).is_file(),
        not (dir_off / CONST_REVIEW_ANALYSIS_FILENAME).exists(),
        "## Model Analysis (Model-Written)" in review_md_on,
        "marker_xyz_987" in review_md_on,
        "## Model Analysis (Model-Written)" not in review_md_off,
    ) == (True, True, True, True, True, True, True, True, True)


def test_score_sessions_and_ai_runs_check_enforce_reference_coverage_tolerance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """score_sessions reads analysis.json reference_coverage and ai runs check gates its drop (#1138, #1147)."""
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path / "data"))

    def _make_scored_session(name: str, numerator: int, denominator: int) -> Path:
        session = tmp_path / name
        (session / "files").mkdir(parents=True)
        (session / "findings.json").write_text(
            json.dumps(
                {
                    "subject": {"type": "path", "ref": "example", "input": "digest123"},
                    "findings": [
                        {"location": "src/a.py:3", "status": "VERIFIED", "severity": "MEDIUM"}
                    ],
                }
            ),
            encoding="utf-8",
        )
        (session / "files" / "page0.json").write_text(
            json.dumps({"file_path": "src/a.py", "findings": [{"location": "src/a.py:3"}]}),
            encoding="utf-8",
        )
        (session / CONST_REVIEW_ANALYSIS_FILENAME).write_text(
            json.dumps(
                {
                    "groups": [],
                    "sampling": {"temperature": 0.1, "top_p": 0.95, "seed": 42},
                    "reference_coverage": {"numerator": numerator, "denominator": denominator},
                    "rejections": {},
                    "model_calls": 1,
                }
            ),
            encoding="utf-8",
        )
        return session

    labels_path = tmp_path / "labels.json"
    labels_path.write_text(
        json.dumps(
            {
                "inputs": [{"name": "in1", "split": "tuning", "digests": ["digest123"]}],
                "labels": [
                    {
                        "identity": {
                            "key": "L1",
                            "producer": "persona",
                            "path": "src/a.py",
                            "start_line": 3,
                            "end_line": 3,
                            "origin": "src/a.py",
                        },
                        "label": "valid-strict",
                        "defect_id": "L1",
                        "note": "ok",
                        "labeller": "tester",
                        "date": "2026-10-17",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    s_base = _make_scored_session("s_base", 4, 4)
    s_curr = _make_scored_session("s_curr", 3, 4)

    rep_base = score_sessions([s_base], labels_path)
    rep_curr = score_sessions([s_curr], labels_path)

    run_base = new_run(
        Mechanism.REVIEW_SCORE,
        setup={"model": "test"},
        subject={"input": "digest123"},
        results=rep_base.run_metrics(),
    )
    run_curr = new_run(
        Mechanism.REVIEW_SCORE,
        setup={"model": "test"},
        subject={"input": "digest123"},
        results=rep_curr.run_metrics(),
    )
    save_run(run_base)
    save_run(run_curr)
    set_baseline(run_base)

    comp = compare_runs(run_base, run_curr)
    strict_check = check_regression(comp, RegressionTolerances(max_reference_coverage_drop=0.10))
    lenient_check = check_regression(comp, RegressionTolerances(max_reference_coverage_drop=0.30))

    cli_fail = cli.invoke(
        app,
        ["ai", "runs", "check", run_curr.run_id, "--max-reference-coverage-drop", "0.10"],
    )
    cli_pass = cli.invoke(
        app,
        ["ai", "runs", "check", run_curr.run_id, "--max-reference-coverage-drop", "0.30"],
    )

    assert (
        rep_base.run_metrics()["reference_coverage"],
        rep_curr.run_metrics()["reference_coverage"],
        strict_check.passed,
        lenient_check.passed,
        cli_fail.exit_code,
        cli_pass.exit_code,
    ) == (1.0, 0.75, False, True, 1, 0)


def test_group_analysis_cut_reply_at_token_cap_is_rejected_not_shown(tmp_path: Path) -> None:
    """A reply cut at token cap (finish_reason=length) is rejected without parsing or showing text (#876)."""
    from devops_cli.review.analysis import (
        render_model_analysis_markdown,
        run_group_analysis,
    )

    source = "def a():\n    return 1\n"
    f1 = _make_region_finding(rule_id="F401", path="src/app.py", line=2, fingerprint="fp-a")
    group_payload = {
        "explanation": "Cut off explanation text that must never be shown.",
        "root_cause": "Root cause text marker.",
        "related_items": [],
        "plan_steps": [{"description": "Step 1", "finding_ids": ["fp-a"]}],
        "doc_quotes": [{"key": "rule:ruff:F401@0.15.10", "text": "unused"}],
        "code_quotes": ["    return 1"],
    }

    # 1. Fake client with finish_reason="length"
    client_cut = _FakeAnalysisClient(
        {"region:src/app.py:a": group_payload},
        finish_reasons=CONST_FINISH_REASON_LENGTH,
    )
    report_cut = run_group_analysis(
        [f1],
        llm_client=client_cut,
        file_contents={"src/app.py": source},
        rule_docs={"rule:ruff:F401@0.15.10": "Module imported but unused."},
        session_dir=tmp_path / "cut",
    )
    persisted_cut = json.loads(
        (tmp_path / "cut" / CONST_REVIEW_ANALYSIS_FILENAME).read_text(encoding="utf-8")
    )
    md_cut = "\n".join(render_model_analysis_markdown(report_cut))

    assert (
        len(client_cut.calls),
        len(report_cut.groups),
        report_cut.groups[0].status,
        report_cut.groups[0].output,
        report_cut.groups[0].rejected_reasons,
        report_cut.rejections,
        persisted_cut["rejections"],
        persisted_cut["groups"][0]["status"],
        persisted_cut["groups"][0]["output"],
        "- **G10 Rejected**: reply-truncated" in md_cut,
        "- **G10 Rejections**: `reply-truncated`: 1" in md_cut,
        "Cut off explanation text" in md_cut,
        "Root cause text marker" in md_cut,
    ) == (
        1,
        1,
        "rejected",
        None,
        [CONST_ANALYSIS_REJECTION_REPLY_TRUNCATED],
        {CONST_ANALYSIS_REJECTION_REPLY_TRUNCATED: 1},
        {CONST_ANALYSIS_REJECTION_REPLY_TRUNCATED: 1},
        "rejected",
        None,
        True,
        True,
        False,
        False,
    )

    # 2. Control: Same payload with finish_reason="stop" parses and verifies
    client_stop = _FakeAnalysisClient(
        {"region:src/app.py:a": group_payload},
        finish_reasons="stop",
    )
    report_stop = run_group_analysis(
        [f1],
        llm_client=client_stop,
        file_contents={"src/app.py": source},
        rule_docs={"rule:ruff:F401@0.15.10": "Module imported but unused."},
        session_dir=tmp_path / "stop",
    )
    md_stop = "\n".join(render_model_analysis_markdown(report_stop))

    assert (
        len(client_stop.calls),
        len(report_stop.groups),
        report_stop.groups[0].status,
        report_stop.groups[0].output is not None,
        report_stop.groups[0].rejected_reasons,
        report_stop.rejections,
        "- **G10 Rejected**" in md_stop,
        "Cut off explanation text" in md_stop,
    ) == (
        1,
        1,
        "verified",
        True,
        [],
        {},
        False,
        True,
    )


def test_group_analysis_multi_group_handles_truncated_and_normal_replies(
    tmp_path: Path,
) -> None:
    """When one group reply is cut and another finishes normally, each is recorded independently (#876)."""
    from devops_cli.review.analysis import (
        render_model_analysis_markdown,
        run_group_analysis,
    )

    source = "def a():\n    return 1\n\ndef b():\n    return 2\n"
    f1 = _make_region_finding(rule_id="F401", path="src/app.py", line=2, fingerprint="fp-a")
    f2 = _make_region_finding(rule_id="F401", path="src/app.py", line=5, fingerprint="fp-b")
    client = _FakeAnalysisClient(
        {
            "region:src/app.py:a": {
                "explanation": "Explanation a.",
                "root_cause": "Root cause a.",
                "related_items": [],
                "plan_steps": [{"description": "Fix a.", "finding_ids": ["fp-a"]}],
                "doc_quotes": [{"key": "rule:ruff:F401@0.15.10", "text": "unused"}],
                "code_quotes": ["    return 1"],
            },
            "region:src/app.py:b": {
                "explanation": "Explanation b.",
                "root_cause": "Root cause b.",
                "related_items": [],
                "plan_steps": [{"description": "Fix b.", "finding_ids": ["fp-b"]}],
                "doc_quotes": [{"key": "rule:ruff:F401@0.15.10", "text": "unused"}],
                "code_quotes": ["    return 2"],
            },
        },
        finish_reasons={
            "region:src/app.py:a": CONST_FINISH_REASON_LENGTH,
            "region:src/app.py:b": "stop",
        },
    )

    report = run_group_analysis(
        [f1, f2],
        llm_client=client,
        file_contents={"src/app.py": source},
        rule_docs={"rule:ruff:F401@0.15.10": "Module imported but unused."},
        session_dir=tmp_path,
    )
    md = "\n".join(render_model_analysis_markdown(report))

    assert (
        len(client.calls),
        len(report.groups),
        report.rejections,
        [g.status for g in report.groups],
        report.groups[0].rejected_reasons,
        report.groups[1].rejected_reasons,
        "- **G10 Rejected**: reply-truncated" in md,
        "Explanation a." in md,
        "Explanation b." in md,
    ) == (
        2,
        2,
        {CONST_ANALYSIS_REJECTION_REPLY_TRUNCATED: 1},
        ["rejected", "verified"],
        [CONST_ANALYSIS_REJECTION_REPLY_TRUNCATED],
        [],
        True,
        False,
        True,
    )


# ── Correlation Table & Review Plan Tests (#1148) ──────────────────────────────


def test_deterministic_cross_group_keys_extraction_and_correlation_table() -> None:
    """Findings extract deterministic cross-group keys and form a sorted correlation table (#1148)."""
    from devops_cli.review.analysis import (
        build_correlation_table,
        extract_finding_correlation_keys,
    )

    f_k8s = _make_k8s_finding(
        rule_id="no-read-only-root-fs",
        path="k8s/llm/profiles/ollama-profiles.yaml",
        logical_location="DaemonSet/ollama-16gib",
        fingerprint="fp-k8s-1",
    )
    f_py = _make_region_finding(
        rule_id="B110",
        path="src/app.py",
        line=10,
        symbol="handle_request",
        fingerprint="fp-py-1",
    )
    f_adv = _make_advisory_finding(
        advisory_id="GHSA-1234",
        path="uv.lock",
        purl="pkg:pypi/httpx2@0.27.0",
        fingerprint="fp-adv-1",
    )

    k8s_keys = extract_finding_correlation_keys(f_k8s)
    py_keys = extract_finding_correlation_keys(
        f_py,
        file_contents={
            "src/app.py": "def handle_request():\n    try:\n        pass\n    except:\n        pass\n"
        },
    )
    adv_keys = extract_finding_correlation_keys(f_adv)

    assert (
        "CWE-284" in k8s_keys["cwe"],
        "kube-linter" in k8s_keys["rule_family"],
        "k8s/llm/profiles/ollama-profiles.yaml" in k8s_keys["manifest_source"],
        "CWE-703" in py_keys["cwe"],
        "broad-except" in py_keys["rule_family"],
        "handle_request" in py_keys["symbol_component"],
        "pkg:pypi/httpx2" in adv_keys["purl"],
    ) == (True, True, True, True, True, True, True)

    table = build_correlation_table([f_k8s, f_py, f_adv])
    assert len(table) >= 4
    # Deterministic sorting by (key_kind, key_value)
    keys_order = [(e.key_kind, e.key_value) for e in table]
    assert keys_order == sorted(keys_order)


def test_g10_check_rejects_unshared_root_cause_key_and_accepts_shared_key() -> None:
    """A 'same root cause' statement is only allowed between findings that share a key (#1148)."""
    from devops_cli.review.analysis import (
        AnalysisJobInput,
        EnvironmentFacts,
        GroupAnalysisOutput,
        PlanStep,
        RelatedItem,
        build_correlation_table,
        verify_group_analysis,
    )

    f1 = _make_k8s_finding(
        rule_id="no-read-only-root-fs",
        path="k8s/deploy1.yaml",
        fingerprint="fp-k8s-1",
    )
    f2 = _make_k8s_finding(
        rule_id="no-read-only-root-fs",
        path="k8s/deploy2.yaml",
        fingerprint="fp-k8s-2",
    )
    f_unrelated = _make_region_finding(
        rule_id="B006",
        path="src/unrelated.py",
        fingerprint="fp-unrelated",
    )

    corr_table = build_correlation_table([f1, f2, f_unrelated])
    job_input = AnalysisJobInput(
        group_id="kubernetes:k8s/deploy1.yaml:Deployment/web",
        kind="kubernetes",
        key=("k8s/deploy1.yaml", "Deployment/web"),
        finding_ids=["fp-k8s-1"],
        finding_summaries=[],
        anchor_regions=[],
        neighbours=[],
        references={},
        needed_keys=[],
        received_keys=[],
        dropped_keys={},
        reference_coverage=1.0,
        environment=EnvironmentFacts(),
    )

    # 1. RelatedItem citing fp-unrelated with same-root-cause -> REJECTED
    out_bad = GroupAnalysisOutput(
        explanation="K8s rootfs issue.",
        root_cause="Shared misconfiguration.",
        plan_steps=[PlanStep(description="Fix rootfs.", finding_ids=["fp-k8s-1"])],
        related_items=[RelatedItem(target="fp-unrelated", relation="same-root-cause")],
    )
    res_bad, reasons_bad = verify_group_analysis(
        out_bad,
        job_input,
        admitted_finding_ids={"fp-k8s-1", "fp-k8s-2", "fp-unrelated"},
        correlation_table=corr_table,
    )
    assert res_bad is None
    assert "unshared-root-cause-key" in reasons_bad

    # 2. Prose root cause citing fp-unrelated -> REJECTED
    out_bad_prose = GroupAnalysisOutput(
        explanation="K8s rootfs issue.",
        root_cause="Has same root cause as fp-unrelated across workloads.",
        plan_steps=[PlanStep(description="Fix rootfs.", finding_ids=["fp-k8s-1"])],
    )
    res_bad_prose, reasons_bad_prose = verify_group_analysis(
        out_bad_prose,
        job_input,
        admitted_finding_ids={"fp-k8s-1", "fp-k8s-2", "fp-unrelated"},
        correlation_table=corr_table,
    )
    assert res_bad_prose is None
    assert "unshared-root-cause-key" in reasons_bad_prose

    # 3. RelatedItem citing fp-k8s-2 (shares rule_family kube-linter and CWE-284) -> VERIFIED
    out_good = GroupAnalysisOutput(
        explanation="K8s rootfs issue.",
        root_cause="Shared misconfiguration.",
        plan_steps=[PlanStep(description="Fix rootfs.", finding_ids=["fp-k8s-1"])],
        related_items=[RelatedItem(target="fp-k8s-2", relation="same-root-cause")],
    )
    res_good, reasons_good = verify_group_analysis(
        out_good,
        job_input,
        admitted_finding_ids={"fp-k8s-1", "fp-k8s-2", "fp-unrelated"},
        correlation_table=corr_table,
    )
    assert res_good is not None
    assert "unshared-root-cause-key" not in reasons_good


def test_review_plan_coverage_and_ordering_g10_checks() -> None:
    """The review plan must cover every finding and order by introduced first, severity, then file (#1148)."""
    from devops_cli.review.analysis import (
        DeferredFinding,
        ReviewPlanOutput,
        ReviewPlanStep,
        build_correlation_table,
        build_deterministic_review_plan,
        verify_review_plan,
    )

    f_crit_intro = _make_region_finding(
        rule_id="B001",
        path="src/a.py",
        line=1,
        fingerprint="fp-crit-intro",
    ).model_copy(update={"severity": "CRITICAL", "introduced": True})

    f_high_intro = _make_region_finding(
        rule_id="B002",
        path="src/b.py",
        line=2,
        fingerprint="fp-high-intro",
    ).model_copy(update={"severity": "HIGH", "introduced": True})

    f_crit_base = _make_region_finding(
        rule_id="B003",
        path="src/c.py",
        line=3,
        fingerprint="fp-crit-base",
    ).model_copy(update={"severity": "CRITICAL", "introduced": False})

    f_low_base = _make_region_finding(
        rule_id="B004",
        path="src/d.py",
        line=4,
        fingerprint="fp-low-base",
    ).model_copy(update={"severity": "LOW", "introduced": False})

    all_findings = [f_low_base, f_crit_base, f_high_intro, f_crit_intro]
    corr_table = build_correlation_table(all_findings)

    # Deterministic plan orders correctly and covers all findings
    plan = build_deterministic_review_plan(all_findings, corr_table)
    verified, reasons = verify_review_plan(plan, all_findings, corr_table)
    assert verified is not None
    assert reasons == []

    # Verify plan step order: introduced first (crit, high), then baseline (crit, low)
    step_fids = [step.finding_ids[0] for step in plan.steps]
    assert step_fids == ["fp-crit-intro", "fp-high-intro", "fp-crit-base", "fp-low-base"]

    # 1. Missing coverage -> REJECTED
    incomplete_plan = ReviewPlanOutput(
        summary="Incomplete plan",
        steps=[plan.steps[0]],
        deferred=[],
    )
    _, inc_reasons = verify_review_plan(incomplete_plan, all_findings, corr_table)
    assert "plan-incomplete-coverage" in inc_reasons

    # 2. Unknown finding cited -> REJECTED
    unknown_plan = ReviewPlanOutput(
        summary="Unknown ID",
        steps=[
            *plan.steps,
            ReviewPlanStep(
                step_number=5, title="Extra", description="Desc", finding_ids=["fp-unknown"]
            ),
        ],
        deferred=[],
    )
    _, unk_reasons = verify_review_plan(unknown_plan, all_findings, corr_table)
    assert "unknown-finding-id" in unk_reasons

    # 3. Violation of order (e.g. baseline crit before intro crit) -> REJECTED
    out_of_order_plan = ReviewPlanOutput(
        summary="Out of order",
        steps=[plan.steps[2], plan.steps[0], plan.steps[1], plan.steps[3]],
        deferred=[],
    )
    _, order_reasons = verify_review_plan(out_of_order_plan, all_findings, corr_table)
    assert "plan-order-violation" in order_reasons

    # 4. Deferred coverage counts towards 100% coverage
    deferred_plan = ReviewPlanOutput(
        summary="With deferred",
        steps=[plan.steps[0], plan.steps[1], plan.steps[2]],
        deferred=[
            DeferredFinding(finding_id="fp-low-base", reason="Low risk baseline issue deferred.")
        ],
    )
    v_def, def_reasons = verify_review_plan(deferred_plan, all_findings, corr_table)
    assert v_def is not None
    assert def_reasons == []


def test_loop_input_groups_9_daemonsets_under_one_step() -> None:
    """On loop input, the plan groups the 9 DaemonSets under one single step (#1148)."""
    from devops_cli.review.analysis import (
        build_correlation_table,
        build_deterministic_review_plan,
        verify_review_plan,
    )

    daemonset_names = [
        "ollama-16gib",
        "ollama-24gib",
        "ollama-32gib",
        "ollama-48gib",
        "ollama-48gib-slow",
        "ollama-64gib",
        "ollama-72gib",
        "ollama-96gib",
        "ollama-128gib",
    ]
    manifest_path = "k8s/llm/profiles/ollama-profiles.yaml"
    ds_findings = [
        _make_k8s_finding(
            rule_id="no-read-only-root-fs",
            path=manifest_path,
            logical_location=f"DaemonSet/{name}",
            fingerprint=f"fp-ds-{idx}",
        )
        for idx, name in enumerate(daemonset_names)
    ]

    corr_table = build_correlation_table(ds_findings)
    # Correlation table must link them by manifest_source, rule_family, and CWE-284
    table_dict = {f"{e.key_kind}:{e.key_value}": e.finding_ids for e in corr_table}
    assert f"manifest_source:{manifest_path}" in table_dict
    assert len(table_dict[f"manifest_source:{manifest_path}"]) == 9
    assert "rule_family:kube-linter" in table_dict
    assert len(table_dict["rule_family:kube-linter"]) == 9
    assert "cwe:CWE-284" in table_dict
    assert len(table_dict["cwe:CWE-284"]) == 9

    plan = build_deterministic_review_plan(ds_findings, corr_table)
    # MUST group all 9 DaemonSets into EXACTLY ONE step
    assert len(plan.steps) == 1
    single_step = plan.steps[0]
    assert len(single_step.finding_ids) == 9
    assert set(single_step.finding_ids) == {f"fp-ds-{idx}" for idx in range(9)}
    assert f"manifest_source:{manifest_path}" in single_step.shared_keys
    assert "rule_family:kube-linter" in single_step.shared_keys
    assert "cwe:CWE-284" in single_step.shared_keys

    verified, reasons = verify_review_plan(plan, ds_findings, corr_table)
    assert verified is not None
    assert reasons == []


def test_correlation_table_and_review_plan_rendered_in_analysis_json_and_review_md(
    tmp_path: Path,
) -> None:
    """analysis.json and review.md include the correlation table and review remediation plan (#1148)."""
    from devops_cli.review.analysis import (
        render_model_analysis_markdown,
        run_group_analysis,
    )

    f1 = _make_k8s_finding(
        rule_id="no-read-only-root-fs",
        path="k8s/deploy.yaml",
        logical_location="DaemonSet/a",
        fingerprint="fp-1",
    )
    f2 = _make_k8s_finding(
        rule_id="no-read-only-root-fs",
        path="k8s/deploy.yaml",
        logical_location="DaemonSet/b",
        fingerprint="fp-2",
    )

    report = run_group_analysis([f1, f2], llm_client=None, session_dir=tmp_path)
    persisted = json.loads((tmp_path / CONST_REVIEW_ANALYSIS_FILENAME).read_text(encoding="utf-8"))
    md = "\n".join(render_model_analysis_markdown(report))

    assert "correlation_table" in persisted
    assert len(persisted["correlation_table"]) > 0
    assert "plan" in persisted
    assert persisted["plan"]["status"] == "verified"
    assert len(persisted["plan"]["output"]["steps"]) == 1

    assert "### Deterministic Cross-Group Correlation Table" in md
    assert "| `manifest_source` | `k8s/deploy.yaml` | `fp-1`, `fp-2` |" in md
    assert "### Review Remediation Plan" in md
    assert (
        "#### Step 1: Remediate no-read-only-root-fs across 2 components in k8s/deploy.yaml" in md
    )
    assert "- **Findings**: `fp-1`, `fp-2`" in md


def test_property_findings_identical_with_stage_on_and_off(tmp_path: Path) -> None:
    """Property test: admitted findings, findings.json, and findings.sarif are identical with stage on vs off (#1148)."""
    from copy import deepcopy

    from devops_cli.review.analysis import run_group_analysis

    f1 = _make_k8s_finding(
        rule_id="no-read-only-root-fs",
        path="k8s/deploy.yaml",
        logical_location="DaemonSet/a",
        fingerprint="fp-k8s-prop-1",
    )
    f2 = _make_region_finding(
        rule_id="B110",
        path="src/app.py",
        line=10,
        symbol="func_prop",
        fingerprint="fp-reg-prop-2",
    )
    f3 = _make_advisory_finding(
        advisory_id="GHSA-9999",
        path="uv.lock",
        fingerprint="fp-adv-prop-3",
    )

    test_findings = [f1, f2, f3]
    baseline_copies = [deepcopy(f) for f in test_findings]

    # Run analysis stage with output to session_dir
    session_on = tmp_path / "stage_on"
    report_on = run_group_analysis(
        test_findings,
        llm_client=None,
        file_contents={"src/app.py": "def func_prop(): pass\n"},
        session_dir=session_on,
    )
    assert report_on.plan is not None

    # 1. In-memory Finding objects are NOT mutated
    assert test_findings == baseline_copies
    assert [f.model_dump() for f in test_findings] == [f.model_dump() for f in baseline_copies]

    # 2. Pipeline generates byte-identical findings.json and findings.sarif with stage on vs off
    source_file = tmp_path / "src" / "app.py"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("import os\n", encoding="utf-8")

    def _run_pipeline(name: str, enable_stage: bool) -> Path:
        s_dir = tmp_path / name
        fake_client = _FakeAnalysisClient({})
        orch = ReviewPipelineOrchestrator(
            session_id="prop-session",
            session_dir=s_dir,
            llm_client=fake_client,
            target_dir=tmp_path,
        )
        orch.admitted_scanner_findings = list(test_findings)
        saved = [
            SavedFinding(
                severity=f.severity,
                location=f.location_display,
                title=f"[{f.tool}] {f.rule_id}",
                description=f.message,
                status="VERIFIED",
                verified=True,
                verified_by=f"static:{f.tool}",
                reportable=True,
                persona="devsecops",
            )
            for f in test_findings
        ]
        payload = FileReviewPayload(
            file_path="src/app.py",
            findings=saved,
            reportable=True,
        )
        orch.generate_consolidated_report(
            [payload],
            stage_flags=ReviewStageFlags(group_analysis=enable_stage),
        )
        return s_dir

    dir_stage_on = _run_pipeline("pipe_on", enable_stage=True)
    dir_stage_off = _run_pipeline("pipe_off", enable_stage=False)

    f_json_on = json.loads(
        (dir_stage_on / CONST_REVIEW_FINDINGS_FILENAME).read_text(encoding="utf-8")
    )
    f_json_off = json.loads(
        (dir_stage_off / CONST_REVIEW_FINDINGS_FILENAME).read_text(encoding="utf-8")
    )
    f_json_on["generated_at"] = f_json_off["generated_at"] = "2026-10-17T00:00:00+00:00"

    sarif_bytes_on = (dir_stage_on / CONST_REVIEW_SARIF_FILENAME).read_bytes()
    sarif_bytes_off = (dir_stage_off / CONST_REVIEW_SARIF_FILENAME).read_bytes()

    assert json.dumps(f_json_on, sort_keys=True) == json.dumps(f_json_off, sort_keys=True)
    assert sarif_bytes_on == sarif_bytes_off
    assert (dir_stage_on / CONST_REVIEW_ANALYSIS_FILENAME).is_file()
    assert not (dir_stage_off / CONST_REVIEW_ANALYSIS_FILENAME).exists()
