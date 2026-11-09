"""`devops roadmap stage`: failure taxonomy and runner capabilities in staging context (#3258).

Staging context includes the failure class table and action rules when the plan cites retry,
review, stop, tier or failure. It includes runner capability facts (image tools, NOT_IN_RUNNER,
and pod security settings) when the plan cites a command or tool name. Both are derived from
repository files at the staged commit, and fail when a source moves or is missing.
"""

from __future__ import annotations

import pytest

from devops_cli.exceptions import RoadmapStageError
from devops_cli.roadmap.stage.stage_context_facts import (
    FAILURE_TAXONOMY_PATH,
    RUNNER_DOCKERFILE_PATH,
    RUNNER_POD_MANIFEST_PATH,
    RUNNER_TOOLS_PATH,
    build_failure_taxonomy_context,
    build_runner_capabilities_context,
    collect_stage_facts_context,
    should_include_failure_taxonomy,
    should_include_runner_capabilities,
)
from tests.support.paths import REPO_ROOT


def _real_repo_read(path: str) -> str | None:
    full_path = REPO_ROOT / path
    if full_path.exists():
        return full_path.read_text("utf-8")
    return None


def test_should_include_failure_taxonomy_triggers_on_keywords() -> None:
    assert should_include_failure_taxonomy("Add a retry for flaky tests")
    assert should_include_failure_taxonomy("Run devops review before ready mark")
    assert should_include_failure_taxonomy("Job stop on timeout")
    assert should_include_failure_taxonomy("Change model tier for retries")
    assert should_include_failure_taxonomy("Handle failure classification")
    assert not should_include_failure_taxonomy("Update documentation styling")


def test_should_include_runner_capabilities_triggers_on_command_or_tools() -> None:
    assert should_include_runner_capabilities("Run devops review on the diff")
    assert should_include_runner_capabilities("Verify with helm template")
    assert should_include_runner_capabilities("Build image with docker")
    assert should_include_runner_capabilities("Check kubectl logs")
    assert not should_include_runner_capabilities("Update markdown readme prose")


def test_retry_plan_gets_failure_taxonomy_in_context() -> None:
    context = collect_stage_facts_context(
        "A plan that advances retry behavior on provider errors",
        _real_repo_read,
    )
    assert "### Failure taxonomy" in context
    assert "provider" in context
    assert "ACTION_BY_CLASS" in context or "retry" in context


def test_plan_without_failure_words_omits_failure_taxonomy() -> None:
    context = collect_stage_facts_context(
        "Just update the project readme description",
        _real_repo_read,
    )
    assert "### Failure taxonomy" not in context


def test_review_command_plan_gets_runner_capabilities_in_context() -> None:
    context = collect_stage_facts_context(
        "A plan that adds devops review to the Job",
        _real_repo_read,
    )
    assert "### Runner capabilities" in context
    assert "Image tools" in context
    assert "NOT_IN_RUNNER" in context
    assert "Pod security settings" in context
    assert "RuntimeDefault" in context
    assert "bwrap" in context or "semgrep" in context


def test_source_move_fails_naming_failure_py() -> None:
    def fake_read(path: str) -> str | None:
        if path == FAILURE_TAXONOMY_PATH:
            return None
        return _real_repo_read(path)

    with pytest.raises(RoadmapStageError) as exc_info:
        build_failure_taxonomy_context(fake_read)
    assert FAILURE_TAXONOMY_PATH in str(exc_info.value)


def test_source_move_fails_naming_runner_tools() -> None:
    def fake_read(path: str) -> str | None:
        if path == RUNNER_TOOLS_PATH:
            return None
        return _real_repo_read(path)

    with pytest.raises(RoadmapStageError) as exc_info:
        build_runner_capabilities_context(fake_read)
    assert RUNNER_TOOLS_PATH in str(exc_info.value)


def test_source_move_fails_naming_pod_manifest() -> None:
    def fake_read(path: str) -> str | None:
        if path == RUNNER_POD_MANIFEST_PATH:
            return None
        return _real_repo_read(path)

    with pytest.raises(RoadmapStageError) as exc_info:
        build_runner_capabilities_context(fake_read)
    assert RUNNER_POD_MANIFEST_PATH in str(exc_info.value)


def test_source_move_fails_naming_dockerfile() -> None:
    def fake_read(path: str) -> str | None:
        if path == RUNNER_DOCKERFILE_PATH:
            return None
        return _real_repo_read(path)

    with pytest.raises(RoadmapStageError) as exc_info:
        build_runner_capabilities_context(fake_read)
    assert RUNNER_DOCKERFILE_PATH in str(exc_info.value)
