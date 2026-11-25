"""Tests for rule-based persona lens selection and bounded telemetry (#4830)."""

from __future__ import annotations

import tomllib

import pytest

from devops_cli.ai.personas import Persona
from devops_cli.ai.personas.lens import (
    FindingSignal,
    LensEvidence,
    load_lens_rules,
    record_lens_choice,
    select_lens,
)
from devops_cli.ai.review.profile import profiling
from devops_cli.config.constants import CONST_AI_MAX_LENS_SERIES
from devops_cli.telemetry.instruments import (
    AI_LENS_TOTAL,
    LENS_COUNTER_CALLERS,
    LENS_COUNTER_LENSES,
    LENS_COUNTER_SOURCES,
)
from devops_cli.telemetry.tracer import trace_span
from tests.support.fakes.otlp import FakeCollector
from tests.support.paths import REPO_ROOT

_LENS_TOML = REPO_ROOT / "src" / "devops_cli" / "ai" / "personas" / "lens.toml"

_EXPECTED_ROW_EVIDENCE: dict[str, tuple[LensEvidence, Persona]] = {
    "flag.explicit": (LensEvidence(explicit_persona=Persona.PM), Persona.PM),
    "step.refute": (LensEvidence(step_role="refute"), Persona.CHALLENGER),
    "finding.gitleaks": (
        LensEvidence(findings=(FindingSignal(producer="gitleaks"),)),
        Persona.DEVSECOPS,
    ),
    "finding.trivy": (
        LensEvidence(findings=(FindingSignal(producer="trivy"),)),
        Persona.DEVSECOPS,
    ),
    "finding.kube-linter": (
        LensEvidence(findings=(FindingSignal(producer="kube-linter"),)),
        Persona.DEVSECOPS,
    ),
    "finding.bandit_cwe": (
        LensEvidence(findings=(FindingSignal(producer="bandit", cwe="CWE-78"),)),
        Persona.DEVSECOPS,
    ),
    "finding.semgrep_cwe": (
        LensEvidence(findings=(FindingSignal(producer="semgrep", cwe="CWE-89"),)),
        Persona.DEVSECOPS,
    ),
    "finding.mypy": (
        LensEvidence(findings=(FindingSignal(producer="mypy"),)),
        Persona.ARCHITECT,
    ),
    "finding.c901": (
        LensEvidence(findings=(FindingSignal(producer="c901"),)),
        Persona.ARCHITECT,
    ),
    "finding.pytest": (
        LensEvidence(findings=(FindingSignal(producer="pytest"),)),
        Persona.QA,
    ),
    "finding.coverage": (
        LensEvidence(findings=(FindingSignal(producer="coverage"),)),
        Persona.QA,
    ),
    "path.k8s": (
        LensEvidence(paths=("k8s/devops/api/deployment.yaml",)),
        Persona.DEVSECOPS,
    ),
    "path.tf": (LensEvidence(paths=("tf/examples/aws/main.tf",)), Persona.DEVSECOPS),
    "path.workflows": (LensEvidence(paths=(".github/workflows/ci.yml",)), Persona.DEVSECOPS),
    "path.dockerfile": (LensEvidence(paths=("Dockerfile.runner",)), Persona.DEVSECOPS),
    "path.tests": (LensEvidence(paths=("tests/ai/test_sample.py",)), Persona.QA),
    "path.adr": (LensEvidence(paths=("docs/adr/0038-example.md",)), Persona.PM),
    "path.docs": (LensEvidence(paths=("docs/ARCHITECTURE.md",)), Persona.PM),
    "path.openspec": (LensEvidence(paths=("openspec/specs/sample/spec.md",)), Persona.PM),
    "path.src": (LensEvidence(paths=("src/devops_cli/cli.py",)), Persona.ARCHITECT),
    "label.type_docs": (LensEvidence(labels=("type/docs",)), Persona.PM),
    "label.type_epic": (LensEvidence(labels=("type/epic",)), Persona.PM),
    "label.type_test": (LensEvidence(labels=("type/test",)), Persona.QA),
    "label.type_security": (LensEvidence(labels=("type/security",)), Persona.DEVSECOPS),
    "label.type_infra": (LensEvidence(labels=("type/infra",)), Persona.DEVSECOPS),
    "label.scope_docs": (LensEvidence(labels=("scope/docs",)), Persona.PM),
    "label.scope_adr": (LensEvidence(labels=("scope/adr",)), Persona.PM),
    "label.scope_spec": (LensEvidence(labels=("scope/spec",)), Persona.PM),
    "label.scope_tests": (LensEvidence(labels=("scope/tests",)), Persona.QA),
    "label.scope_security": (LensEvidence(labels=("scope/security",)), Persona.DEVSECOPS),
    "label.scope_k8s": (LensEvidence(labels=("scope/k8s",)), Persona.DEVSECOPS),
    "label.scope_infra": (LensEvidence(labels=("scope/infra",)), Persona.DEVSECOPS),
    "label.scope_terraform": (LensEvidence(labels=("scope/terraform",)), Persona.DEVSECOPS),
    "label.scope_ci": (LensEvidence(labels=("scope/ci",)), Persona.DEVSECOPS),
    "label.scope_monitoring": (LensEvidence(labels=("scope/monitoring",)), Persona.DEVSECOPS),
    "label.scope_deps": (LensEvidence(labels=("scope/deps",)), Persona.DEVSECOPS),
    "label.type_other": (LensEvidence(labels=("type/feature",)), Persona.ARCHITECT),
    "label.scope_other": (LensEvidence(labels=("scope/cli",)), Persona.ARCHITECT),
}


def test_lens_toml_rows_load_in_order_with_unique_ids_and_full_table_coverage() -> None:
    """Every row in `lens.toml` has a unique id in file order and a matching test case (#4830)."""
    raw_rows = tomllib.loads(_LENS_TOML.read_text(encoding="utf-8"))["rules"]
    loaded = load_lens_rules()
    raw_ids = [row["id"] for row in raw_rows]
    loaded_ids = [rule.id for rule in loaded]

    assert loaded_ids == raw_ids
    assert len(loaded_ids) == len(set(loaded_ids))
    assert set(loaded_ids) == set(_EXPECTED_ROW_EVIDENCE)


@pytest.mark.parametrize("rule_id", list(_EXPECTED_ROW_EVIDENCE))
def test_every_lens_toml_row_matches_its_declared_rule_and_lens(rule_id: str) -> None:
    """Each row in `lens.toml` returns its expected lens and rule id (#4830)."""
    evidence, expected_persona = _EXPECTED_ROW_EVIDENCE[rule_id]
    choice = select_lens(evidence)

    assert (choice.lens, choice.rule_id) == (expected_persona, rule_id)


def test_first_match_precedence_and_cwe_gate() -> None:
    """Flag beats path, refute beats finding, path beats label, and bandit without CWE skips (#4830)."""
    flag_wins = select_lens(
        LensEvidence(
            explicit_persona=Persona.PM,
            step_role="refute",
            paths=("k8s/devops/api/deployment.yaml",),
        )
    )
    refute_wins = select_lens(
        LensEvidence(
            step_role="refute",
            findings=(FindingSignal(producer="gitleaks"),),
            paths=("k8s/devops/api/deployment.yaml",),
        )
    )
    path_beats_label = select_lens(
        LensEvidence(
            paths=("src/devops_cli/cli.py",),
            labels=("type/docs",),
        )
    )
    bandit_no_cwe = select_lens(LensEvidence(findings=(FindingSignal(producer="bandit"),)))
    empty_choice = select_lens(LensEvidence())

    assert (flag_wins.lens, flag_wins.rule_id, flag_wins.source) == (
        Persona.PM,
        "flag.explicit",
        "flag",
    )
    assert (refute_wins.lens, refute_wins.rule_id, refute_wins.source) == (
        Persona.CHALLENGER,
        "step.refute",
        "rule",
    )
    assert (path_beats_label.lens, path_beats_label.rule_id, path_beats_label.source) == (
        Persona.ARCHITECT,
        "path.src",
        "rule",
    )
    assert (bandit_no_cwe.lens, bandit_no_cwe.rule_id, bandit_no_cwe.source) == (None, "", "none")
    assert (empty_choice.lens, empty_choice.rule_id, empty_choice.source) == (None, "", "none")


def test_lens_counter_series_product_stays_within_84_and_records_span_and_profile(
    otlp: FakeCollector,
) -> None:
    """Counter label product <= 84 and record_lens_choice writes span, profile, and counter (#4830)."""
    series_product = (
        len(LENS_COUNTER_CALLERS) * len(LENS_COUNTER_LENSES) * len(LENS_COUNTER_SOURCES)
    )
    assert series_product <= CONST_AI_MAX_LENS_SERIES == 84

    choice = select_lens(LensEvidence(paths=("k8s/devops/api/deployment.yaml",)))
    with profiling() as profiler, trace_span("test.lens") as span:
        record_lens_choice(choice, caller="chat", span=span, profiler=profiler)
        profile = profiler.build(session_id="s1", target="t1")

    span_attrs = next(s.attributes for s in otlp.spans if s.name == "test.lens")
    points = otlp.points(AI_LENS_TOTAL.name)
    assert (
        span_attrs.get("ai.lens"),
        span_attrs.get("ai.lens.rule"),
        profile.lens,
        profile.lens_rule,
        bool(profile.prompt_digest),
    ) == ("devsecops", "path.k8s", "devsecops", "path.k8s", True)
    assert any(
        attrs == {"caller": "chat", "lens": "devsecops", "source": "rule"} and value == 1.0
        for attrs, value in points
    )
