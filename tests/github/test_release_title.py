"""A hidden release type cannot ship runtime code (#5224)."""

from __future__ import annotations

from devops_cli.github.release_title import hidden_type_problem, hidden_types

CONFIG = {
    "changelog-sections": [
        {"type": "feat", "section": "Features"},
        {"type": "fix", "section": "Bug Fixes"},
        {"type": "refactor", "section": "Code Refactoring"},
        {"type": "docs", "section": "Documentation", "hidden": True},
        {"type": "chore", "section": "Chores", "hidden": True},
    ]
}


def test_the_hidden_types_come_from_the_config() -> None:
    assert hidden_types(CONFIG) == {"docs", "chore"}


def test_a_docs_title_with_code_is_refused_naming_the_types_and_the_path() -> None:
    problem = hidden_type_problem(
        "docs(cli): remove the sync", ["src/devops_cli/commands/docs.py"], CONFIG
    )

    assert problem is not None
    assert (
        "docs" in problem,
        "`feat`" in problem,
        "src/devops_cli/commands/docs.py" in problem,
    ) == (
        True,
        True,
        True,
    )


def test_a_docs_title_with_documents_only_passes() -> None:
    paths = ["docs/CLI_REFERENCE.md", "src/devops_cli/ai/knowledge_base/tools/helm.md"]

    assert hidden_type_problem("docs(cli): a page", paths, CONFIG) is None


def test_a_shown_type_with_code_passes() -> None:
    assert (
        hidden_type_problem("refactor(cli): remove it", ["src/devops_cli/commands/docs.py"], CONFIG)
        is None
    )


def test_a_changed_config_changes_the_verdict() -> None:
    config = {
        "changelog-sections": [
            {"type": "feat", "section": "Features", "hidden": True},
        ]
    }

    assert hidden_types(config) == {"feat"}
    assert (
        hidden_type_problem("feat(cli): a change", ["src/devops_cli/commands/docs.py"], config)
        is not None
    )
