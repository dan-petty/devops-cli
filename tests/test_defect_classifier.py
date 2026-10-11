"""Unit tests for defect PR classification and declared hardening surface detection (#697)."""

from __future__ import annotations

from devops_cli.github.defect_classifier import (
    audit_pr_hardening,
    classify_defect_pr,
    is_defect_pr,
    match_hardening_surface,
)


def test_defect_classifier_by_labels() -> None:
    """Classify PRs with type/bug and type/security labels as defects."""
    bug_res = classify_defect_pr("feat(cli): new flag", labels=["type/bug"])
    sec_res = classify_defect_pr("refactor(k8s): clean up", labels=["type/security"])
    dict_labels_res = classify_defect_pr(
        "chore(deps): bump httpx2", labels=[{"name": "type/bug"}, {"name": "scope/cli"}]
    )
    non_defect_res = classify_defect_pr("feat(cli): command", labels=["type/feature", "scope/cli"])

    assert (
        bug_res.is_defect,
        bug_res.has_bug_label,
        bug_res.has_security_label,
        bug_res.has_fix_title,
    ) == (True, True, False, False)

    assert (
        sec_res.is_defect,
        sec_res.has_bug_label,
        sec_res.has_security_label,
        sec_res.has_fix_title,
    ) == (True, False, True, False)

    assert (
        dict_labels_res.is_defect,
        dict_labels_res.has_bug_label,
        non_defect_res.is_defect,
    ) == (True, True, False)


def test_defect_classifier_by_title() -> None:
    """Classify PRs with fix(...) or fix: title prefixes as defects."""
    titles_expected = [
        ("fix: crash on invalid configuration", True),
        ("fix(ci): update runner image to ubuntu-24.04", True),
        ("fix(k8s)!: remove legacy service alias", True),
        ("fix!: drop deprecated parameter", True),
        ("Fix(ai): handle null model response", True),
        ("feat(github): add hardening report command", False),
        ("refactor(output): consolidate tables", False),
        ("docs: fix typo in README", False),
        ("chore(deps): update lockfile", False),
    ]

    results = [(title, is_defect_pr(title, labels=[])) for title, _ in titles_expected]
    assert results == titles_expected


def test_defect_classifier_combined_and_reasons() -> None:
    """Verify classification reasons aggregation across labels and title."""
    both = classify_defect_pr("fix(k8s): resolve pod restart", labels=["type/bug", "type/security"])
    neither = classify_defect_pr("feat(cli): add command", labels=["type/feature"])

    assert (
        both.is_defect,
        both.has_bug_label,
        both.has_security_label,
        both.has_fix_title,
        set(both.reasons),
    ) == (
        True,
        True,
        True,
        True,
        {"label:type/bug", "label:type/security", "title:fix"},
    )

    assert (neither.is_defect, neither.reasons) == (False, ())


def test_match_hardening_surface_declared_surfaces() -> None:
    """Verify that only the declared hardening surfaces match, and docs/ROADMAP.md is excluded."""
    test_paths = [
        ("AGENTS.md", "AGENTS.md"),
        ("src/devops_cli/ai/tasks/review.md", "src/devops_cli/ai/tasks/*.md"),
        ("src/devops_cli/ai/tasks/nested/deep.md", None),
        ("src/devops_cli/ai/knowledge_base/README.md", "src/devops_cli/ai/knowledge_base/"),
        (
            "src/devops_cli/ai/knowledge_base/topics/security.md",
            "src/devops_cli/ai/knowledge_base/",
        ),
        ("common_hallucinations.json", "common_hallucinations.json"),
        ("src/devops_cli/ai/review/common_hallucinations.json", "common_hallucinations.json"),
        (".data/common_hallucinations.json", "common_hallucinations.json"),
        ("docs/ROADMAP.md", None),  # strictly excluded generated view
        ("docs/CLI_REFERENCE.md", None),
        ("src/devops_cli/commands/pr.py", None),
        ("tests/test_ci.py", None),
    ]

    actual = [(path, match_hardening_surface(path)) for path, _ in test_paths]
    assert actual == test_paths


def test_audit_pr_hardening_with_additions() -> None:
    """Audit PR hardening when additions are present on declared surfaces."""
    files = [
        {"path": "src/devops_cli/commands/pr.py", "additions": 45, "deletions": 2},
        {"path": "AGENTS.md", "additions": 12, "deletions": 0},
        {"path": "src/devops_cli/ai/tasks/verify.md", "additions": 8, "deletions": 1},
        {"path": "docs/ROADMAP.md", "additions": 50, "deletions": 0},  # excluded
    ]

    audit = audit_pr_hardening(
        pr_number=697,
        title="fix(github): defect PR hardening audit",
        labels=["type/bug"],
        files=files,
    )

    assert (
        audit.is_hardened,
        audit.empty_file_list,
        audit.total_files,
        audit.hardened_surfaces,
        audit.surface_additions["AGENTS.md"],
        audit.surface_additions["src/devops_cli/ai/tasks/*.md"],
    ) == (
        True,
        False,
        4,
        ("AGENTS.md", "src/devops_cli/ai/tasks/*.md"),
        12,
        8,
    )


def test_audit_pr_hardening_missing_additions() -> None:
    """Audit PR hardening when zero additions exist on declared surfaces."""
    files = [
        {"path": "src/devops_cli/commands/pr.py", "additions": 30, "deletions": 10},
        {"path": "tests/test_pr.py", "additions": 50, "deletions": 0},
        {"path": "AGENTS.md", "additions": 0, "deletions": 5},  # deletions only
        {"path": "docs/ROADMAP.md", "additions": 25, "deletions": 0},  # excluded
    ]

    audit = audit_pr_hardening(
        pr_number=698,
        title="fix(cli): bug fix without guardrail",
        labels=["type/bug"],
        files=files,
    )

    assert (
        audit.is_hardened,
        audit.hardened_surfaces,
        audit.empty_file_list,
        audit.surface_additions["AGENTS.md"],
    ) == (
        False,
        (),
        False,
        0,
    )


def test_audit_pr_hardening_empty_file_list() -> None:
    """Audit PR hardening with empty file list reports empty_file_list error state."""
    audit = audit_pr_hardening(
        pr_number=699,
        title="fix(cli): empty PR",
        labels=["type/bug"],
        files=[],
    )

    assert (
        audit.empty_file_list,
        audit.is_hardened,
        audit.total_files,
    ) == (
        True,
        False,
        0,
    )
