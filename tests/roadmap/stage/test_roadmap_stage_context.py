"""`devops roadmap stage`: failure taxonomy and runner capabilities in staging context (#3258).

Staging context includes the failure class table and action rules when the plan cites retry,
review, stop, tier or failure. It includes the runner tools and NOT_IN_RUNNER when the plan cites a
command or tool name. Both come from the installed modules, because the runner image is the
devops-cli image for every repository (#4628). The Dockerfile packages and the pod security
settings come from the staged commit, and only when that commit is a devops-cli commit.
"""

from __future__ import annotations

from devops_cli.roadmap.runner_tools import NOT_IN_RUNNER
from devops_cli.roadmap.stage.stage_context_facts import (
    RUNNER_DOCKERFILE_PATH,
    RUNNER_POD_MANIFEST_PATH,
    RUNNER_TOOLS_PATH,
    collect_stage_facts_context,
    should_include_failure_taxonomy,
    should_include_runner_capabilities,
)
from tests.support.paths import REPO_ROOT


def _no_file(path: str) -> str | None:
    """The read of a staged commit that holds none of the devops-cli files."""
    del path
    return None


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


def test_a_retry_text_gets_the_failure_taxonomy_from_a_commit_of_another_repository() -> None:
    context = collect_stage_facts_context("Add a retry to the backup script", _no_file)

    assert "### Failure taxonomy" in context
    assert "- `provider`: `retry`" in context


def test_a_uv_text_gets_the_runner_tools_from_a_commit_of_another_repository() -> None:
    context = collect_stage_facts_context("Install the tools with uv", _no_file)

    assert "- Runner tools: `uv`, " in context
    assert f"- `helm`: {NOT_IN_RUNNER['helm']}" in context
    assert "Installed packages" not in context
    assert "Pod security settings" not in context


def test_the_dockerfile_of_another_repository_gives_no_image_facts() -> None:
    """Only a commit that holds `runner_tools.py` describes the runner image. Another repository
    can hold a Dockerfile and a pod manifest for its own image."""
    other = {
        RUNNER_DOCKERFILE_PATH: "FROM example.com/base AS runner\nRUN apt-get install -y git\n",
        RUNNER_POD_MANIFEST_PATH: _real_repo_read(RUNNER_POD_MANIFEST_PATH),
    }

    context = collect_stage_facts_context("Install the tools with uv", other.get)

    assert "### Runner capabilities" in context
    assert "Installed packages" not in context
    assert "Pod security settings" not in context


def test_each_not_in_runner_line_holds_its_reason_text() -> None:
    context = collect_stage_facts_context("Run devops review on the diff", _real_repo_read)

    lines = context.splitlines()
    missing = [
        prog for prog, reason in NOT_IN_RUNNER.items() if f"- `{prog}`: {reason}" not in lines
    ]

    assert missing == []


def test_the_runner_fact_files_exist_in_the_repository() -> None:
    """A move of a fact file of the staged commit fails here, and not in a Job of the Service."""
    paths = (RUNNER_TOOLS_PATH, RUNNER_DOCKERFILE_PATH, RUNNER_POD_MANIFEST_PATH)

    assert [path for path in paths if not (REPO_ROOT / path).is_file()] == []
