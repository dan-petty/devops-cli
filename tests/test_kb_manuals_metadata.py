"""Tests for Knowledge Base manual version metadata, loader matching, and review drift reporting (#1149)."""

from __future__ import annotations

from pathlib import Path

from devops_cli.ai.kb import (
    DriftManual,
    MatchedManual,
    filter_kb_manuals_for_group,
    get_knowledge_base_dir,
    list_knowledge_base_articles,
    load_matched_kb_manuals,
    parse_manual_front_matter,
)
from devops_cli.config.constants import (
    CONST_KB_METADATA_TARGET_SUBDIRS,
    CONST_KB_REFERENCE_PREFIX,
    CONST_KB_SHA_DIGEST_LENGTH,
)
from devops_cli.review.analysis import (
    AnalysisReport,
    EnvironmentFacts,
    FindingGroup,
    RatioRecord,
    SamplingRecord,
    _collect_reference_candidates,
    render_model_analysis_markdown,
    run_group_analysis,
)
from devops_cli.review.anchors import ToolAnchor
from devops_cli.review.finding import Finding
from devops_cli.review.state import FindingState


def _make_dummy_finding(
    *,
    tool: str = "bandit",
    tool_version: str = "1.9.4",
    rule_id: str = "B101",
    path: str = "src/app.py",
    line: int = 10,
    fingerprint: str = "fp-1",
    logical_location: str = "",
) -> Finding:
    return Finding(
        anchor=ToolAnchor(run_id="run-1", result_index=0, rule_id=rule_id),
        tool=tool,
        tool_version=tool_version,
        rule_id=rule_id,
        path=path,
        line=line,
        end_line=line,
        logical_location=logical_location,
        message=f"{tool} finding {rule_id}",
        description=f"Description for {rule_id}",
        severity="MEDIUM",
        severity_derivation="rule",
        state=FindingState.OPEN,
        fingerprint_v2=fingerprint,
    )


def test_every_target_manual_has_valid_front_matter() -> None:
    """Every it_domains manual and devops_cli/libraries guide gains valid front-matter (#1149)."""
    kb_dir = get_knowledge_base_dir()
    target_articles: list[Path] = []
    for sub in CONST_KB_METADATA_TARGET_SUBDIRS:
        target_articles.extend(list_knowledge_base_articles(sub))

    assert len(target_articles) == 60

    for article in target_articles:
        rel = article.relative_to(kb_dir).as_posix()
        content = article.read_text(encoding="utf-8")
        assert content.startswith("---\n"), f"{rel} does not start with front-matter delimiter"

        fm, body, error = parse_manual_front_matter(content)
        assert error is None, f"{rel} failed front-matter parse: {error}"
        assert fm is not None, f"{rel} returned no front-matter"
        assert len(fm.applies_to) > 0, f"{rel} has empty applies_to"
        assert len(fm.sources) > 0, f"{rel} has empty sources"
        assert all(s.startswith(("http://", "https://")) for s in fm.sources), (
            f"{rel} invalid sources"
        )
        assert len(fm.reviewed) == 10, f"{rel} invalid reviewed date format: {fm.reviewed}"
        assert len(body.strip()) > 0, f"{rel} body is empty"


def test_loader_matches_tools_lock_inventory_floor_and_kubernetes() -> None:
    """Loader matches applies_to against tools lock, inventory, floor and kubernetes (#1149)."""
    env = EnvironmentFacts(
        language_floor="py314",
        python_pin="3.14",
        tool_versions={"bandit": "1.9.4", "semgrep": "1.179.0", "kube-linter": "0.8.3"},
        locked_packages={"pkg:pypi/pydantic": ["2.13.5"], "pkg:pypi/ruff": ["0.16.8"]},
        kubernetes_version="v1.31.0",
    )
    matched, _drift = load_matched_kb_manuals(environment=env, kubernetes_version="v1.31.0")

    assert len(matched) >= 40
    matched_paths = {m.path for m in matched}
    assert "it_domains/tools/bandit.md" in matched_paths
    assert "devops_cli/libraries/bandit_actionlint.md" in matched_paths
    assert "devops_cli/libraries/pydantic.md" in matched_paths
    assert "it_domains/tools/semgrep.md" in matched_paths
    assert "it_domains/topics/cloud_native_kubernetes_and_gitops.md" in matched_paths

    # Verify reference item format kb:<path>@<sha>
    for m in matched:
        assert m.key.startswith(CONST_KB_REFERENCE_PREFIX)
        assert "@" in m.key
        _prefix, sha = m.key.rsplit("@", 1)
        assert len(sha) == CONST_KB_SHA_DIGEST_LENGTH


def test_loader_excludes_mismatched_and_undated_manuals(tmp_path: Path) -> None:
    """Mismatched versions or undated manuals are excluded and tracked in drift (#1149)."""
    fake_kb = tmp_path / "kb"
    tools_dir = fake_kb / "it_domains" / "tools"
    libs_dir = fake_kb / "devops_cli" / "libraries"
    tools_dir.mkdir(parents=True)
    libs_dir.mkdir(parents=True)

    # 1. Undated manual
    (tools_dir / "undated.md").write_text(
        '---\napplies_to:\n  - "tool:bandit@1.9.*"\nsources:\n  - "https://example.com"\nreviewed: "invalid-date"\n---\n\n# Undated\n',
        encoding="utf-8",
    )
    # 2. Missing sources
    (tools_dir / "nosources.md").write_text(
        '---\napplies_to:\n  - "tool:bandit@1.9.*"\nsources: []\nreviewed: "2026-10-15"\n---\n\n# No Sources\n',
        encoding="utf-8",
    )
    # 3. Mismatched tool version
    (tools_dir / "mismatched_tool.md").write_text(
        '---\napplies_to:\n  - "tool:bandit@2.0.*"\nsources:\n  - "https://example.com"\nreviewed: "2026-10-15"\n---\n\n# Tool Mismatch\n',
        encoding="utf-8",
    )
    # 4. Mismatched python floor
    (libs_dir / "mismatched_py.md").write_text(
        '---\napplies_to:\n  - "python>=3.16"\nsources:\n  - "https://example.com"\nreviewed: "2026-10-15"\n---\n\n# Python Mismatch\n',
        encoding="utf-8",
    )
    # 5. Mismatched pkg version
    (libs_dir / "mismatched_pkg.md").write_text(
        '---\napplies_to:\n  - "pkg:pypi/pydantic@1.*"\nsources:\n  - "https://example.com"\nreviewed: "2026-10-15"\n---\n\n# Pkg Mismatch\n',
        encoding="utf-8",
    )
    # 6. Mismatched k8s
    (tools_dir / "mismatched_k8s.md").write_text(
        '---\napplies_to:\n  - "k8s@1.28.*"\nsources:\n  - "https://example.com"\nreviewed: "2026-10-15"\n---\n\n# K8s Mismatch\n',
        encoding="utf-8",
    )
    # 7. Valid matching manual
    (tools_dir / "valid.md").write_text(
        '---\napplies_to:\n  - "tool:bandit@1.9.*"\nsources:\n  - "https://example.com"\nreviewed: "2026-10-15"\n---\n\n# Valid Manual\n',
        encoding="utf-8",
    )

    env = EnvironmentFacts(
        language_floor="py314",
        python_pin="3.14",
        tool_versions={"bandit": "1.9.4"},
        locked_packages={"pkg:pypi/pydantic": ["2.13.5"]},
        kubernetes_version="v1.31.0",
    )
    matched, drift = load_matched_kb_manuals(
        kb_dir=fake_kb, environment=env, kubernetes_version="v1.31.0"
    )

    assert len(matched) == 1
    assert matched[0].path == "it_domains/tools/valid.md"

    drift_by_path = {d.path: d.reason for d in drift}
    assert "it_domains/tools/undated.md" in drift_by_path
    assert "invalid front-matter" in drift_by_path["it_domains/tools/undated.md"]

    assert "it_domains/tools/nosources.md" in drift_by_path
    assert "invalid front-matter" in drift_by_path["it_domains/tools/nosources.md"]

    assert "it_domains/tools/mismatched_tool.md" in drift_by_path
    assert (
        "mismatched tool bandit: requires 2.0.*, found 1.9.4"
        in drift_by_path["it_domains/tools/mismatched_tool.md"]
    )

    assert "devops_cli/libraries/mismatched_py.md" in drift_by_path
    assert (
        "mismatched python: requires python>=3.16, found 3.14"
        in drift_by_path["devops_cli/libraries/mismatched_py.md"]
    )

    assert "devops_cli/libraries/mismatched_pkg.md" in drift_by_path
    assert (
        "mismatched pkg pypi/pydantic: requires 1.*, found 2.13.5"
        in drift_by_path["devops_cli/libraries/mismatched_pkg.md"]
    )

    assert "it_domains/tools/mismatched_k8s.md" in drift_by_path
    assert (
        "mismatched kubernetes: requires 1.28.*, found v1.31.0"
        in drift_by_path["it_domains/tools/mismatched_k8s.md"]
    )


def test_group_analysis_receives_producing_tool_and_rule_family_manuals() -> None:
    """Group analysis jobs receive matched manuals for producing tool and rule family (#1149)."""
    f_bandit = _make_dummy_finding(tool="bandit", rule_id="B101", fingerprint="fp-b1")
    f_k8s = _make_dummy_finding(
        tool="kube-linter",
        rule_id="no-read-only-root-fs",
        path="k8s/deploy.yaml",
        logical_location="Deployment/web",
        fingerprint="fp-k1",
    )
    g_bandit = FindingGroup(
        group_id="g-bandit", kind="region", key=("src/app.py", "f"), findings=(f_bandit,)
    )
    g_k8s = FindingGroup(
        group_id="g-k8s",
        kind="kubernetes",
        key=("k8s/deploy.yaml", "Deployment/web"),
        findings=(f_k8s,),
    )

    matched_manuals = [
        MatchedManual(
            path="it_domains/tools/bandit.md",
            key="kb:it_domains/tools/bandit.md@1234",
            content="Bandit security tool documentation.",
            tools=("bandit",),
            topics=(),
            tags=("bandit", "security"),
            sha="1234",
        ),
        MatchedManual(
            path="it_domains/tools/kubelinter_popeye_pluto.md",
            key="kb:it_domains/tools/kubelinter_popeye_pluto.md@5678",
            content="KubeLinter kubernetes quality documentation.",
            tools=("kube-linter", "kubelinter"),
            topics=(),
            tags=("k8s", "kube-linter"),
            sha="5678",
        ),
    ]

    bandit_kb = filter_kb_manuals_for_group(g_bandit, matched_manuals)
    assert "kb:it_domains/tools/bandit.md@1234" in bandit_kb
    assert "kb:it_domains/tools/kubelinter_popeye_pluto.md@5678" not in bandit_kb

    k8s_kb = filter_kb_manuals_for_group(g_k8s, matched_manuals)
    assert "kb:it_domains/tools/kubelinter_popeye_pluto.md@5678" in k8s_kb
    assert "kb:it_domains/tools/bandit.md@1234" not in k8s_kb


def test_official_rule_docs_rank_first_before_kb_manuals() -> None:
    """Official rule docs rank first before matched KB manuals in reference candidate list (#1149)."""
    f = _make_dummy_finding(tool="bandit", rule_id="B101")
    g = FindingGroup(group_id="g-1", kind="region", key=("src/app.py", "f"), findings=(f,))

    rule_docs = {"rule:bandit:B101@1.9.4": "Official Bandit B101 rule documentation."}
    kb_manuals = {"kb:it_domains/tools/bandit.md@1234": "General Bandit tool guide."}

    candidates = _collect_reference_candidates(
        g,
        rule_docs=rule_docs,
        kb_manuals=kb_manuals,
        tool_versions={"bandit": "1.9.4"},
    )

    assert len(candidates) == 2
    # Official rule doc is first candidate
    assert candidates[0][0] == "rule:bandit:B101@1.9.4"
    assert candidates[0][1] == "Official Bandit B101 rule documentation."
    # Matched KB manual follows
    assert candidates[1][0] == "kb:it_domains/tools/bandit.md@1234"
    assert candidates[1][1] == "General Bandit tool guide."


def test_review_markdown_includes_reference_coverage_drift() -> None:
    """review.md lists drifted manuals under 'Reference coverage: drift' (#1149)."""
    drift = [
        DriftManual(
            path="it_domains/tools/grafana.md",
            reason="tool:grafana not found in tools.lock or environment",
        ),
        DriftManual(
            path="devops_cli/libraries/example.md",
            reason="mismatched python: requires python>=3.16, found 3.14",
        ),
    ]
    report = AnalysisReport(
        groups=[],
        correlation_table=[],
        sampling=SamplingRecord(temperature=0.1, top_p=0.95, seed=42),
        reference_coverage=RatioRecord(numerator=2, denominator=2),
        rejections={},
        dispatched=0,
        replayed=0,
        failed=0,
        drift_manuals=drift,
        injected_manuals=["kb:it_domains/tools/bandit.md@1234"],
    )

    lines = render_model_analysis_markdown(report)
    md = "\n".join(lines)

    assert "### Reference coverage: injected" in md
    assert "- `kb:it_domains/tools/bandit.md@1234`" in md
    assert "### Reference coverage: drift" in md
    assert (
        "- `it_domains/tools/grafana.md`: tool:grafana not found in tools.lock or environment" in md
    )
    assert (
        "- `devops_cli/libraries/example.md`: mismatched python: requires python>=3.16, found 3.14"
        in md
    )


def test_run_group_analysis_populates_kb_drift_and_injected() -> None:
    """run_group_analysis loads matched KB manuals, injects them into jobs and logs drift (#1149)."""
    f = _make_dummy_finding(tool="bandit", rule_id="B101")
    report = run_group_analysis([f], llm_client=None)

    assert len(report.drift_manuals) > 0
    drift_paths = {d.path for d in report.drift_manuals}
    assert "it_domains/tools/grafana.md" in drift_paths
    md = "\n".join(render_model_analysis_markdown(report))
    assert "Reference coverage: drift" in md


def test_floor_only_environment_matches_and_drifts_manuals_and_filtering_keeps_some() -> None:
    """A floor-only environment matches some manuals and drifts others, and filtering keeps some for a group (#1149)."""
    env = EnvironmentFacts(language_floor="py314", python_pin="3.14", kubernetes_version="v1.31.0")
    matched, drift = load_matched_kb_manuals(environment=env)
    assert len(matched) > 0
    assert len(drift) > 0

    f = _make_dummy_finding(tool="bandit", rule_id="B101")
    g = FindingGroup(group_id="g-1", kind="region", key=("src/app.py", "f"), findings=(f,))
    filtered = filter_kb_manuals_for_group(g, matched)
    assert len(filtered) > 0
