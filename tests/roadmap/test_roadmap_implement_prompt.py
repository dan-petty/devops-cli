"""The prompt of the implement step tells the agent where its scratch files go (#3006): the step
commits every file in the checkout, so a scratch file outside the ignored directory would reach
the pull request.

It keeps what is specific to the runner and leaves the rules of the project to `AGENTS.md`, which
the message of the step holds (#3097). A rule in two places drifts, so a test compares what it can.
"""

from __future__ import annotations

import pytest

from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.roadmap.step_files import code_spans
from tests.support.paths import REPO_ROOT

PROMPT = "roadmap_implement_step.md"
SCRATCH_DIRECTORY = ".data/agent/scratch/"
DATA_ROOT = ".data/"
# The rules that `AGENTS.md` and the documents it routes to own. The prompt once copied them, and
# one copy said "nesting of 5" where `CONTRIBUTING.md` says 4.
DROPPED_RULES = (
    "Use an open library or the standard library before you write a helper",
    "Write no code in the product that detects a test",
    "Swallow no error",
    "Keep the complexity of a function",
    "Write the prose of documents, messages and comments",
    "Write no secret, internal host name",
    "Do not edit `CHANGELOG.md`",
)


def _data_paths(text: str) -> set[str]:
    """The code spans of `text` that are a path under `.data/`."""
    return {span for span in code_spans(text) if span.startswith(DATA_ROOT)}


def test_the_prompt_names_the_ignored_scratch_directory() -> None:
    prompt = load_task_prompt(PROMPT)

    assert SCRATCH_DIRECTORY in prompt


def test_the_prompt_keeps_scratch_files_out_of_the_checkout_root() -> None:
    prompt = load_task_prompt(PROMPT)

    assert "Put no scratch file in the checkout root" in prompt


def test_the_prompt_says_that_the_step_deletes_a_file_that_the_group_does_not_name() -> None:
    """The step removes a stray file before its checks (#3092), and the prompt says so."""
    prompt = load_task_prompt(PROMPT)

    assert "The step deletes a new file that your group does not name" in prompt


def test_the_prompt_says_that_the_hooks_of_the_project_run_and_that_a_failure_gives_a_turn() -> (
    None
):
    """The step runs the `pre-commit` stage on the changed files (#3043), and the agent learns that
    a failed hook gives it a turn with the output."""
    prompt = load_task_prompt(PROMPT)

    assert "The step runs the hooks of the project on your changed files" in prompt
    assert "A hook that still fails gives you another turn" in prompt


def test_the_prompt_leaves_the_rules_of_agents_md_to_that_file() -> None:
    prompt = load_task_prompt(PROMPT)

    assert [rule for rule in DROPPED_RULES if rule in prompt] == []


def test_the_prompt_names_the_section_that_holds_the_rules() -> None:
    from devops_cli.roadmap.step_rules import RULES_HEADING

    prompt = load_task_prompt(PROMPT)

    assert f'"{RULES_HEADING}"' in prompt


def test_every_data_path_of_the_prompt_is_a_data_path_of_agents_md() -> None:
    agents = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")

    assert _data_paths(load_task_prompt(PROMPT)) <= _data_paths(agents)


def test_the_scratch_directory_is_the_same_in_the_prompt_and_in_agents_md() -> None:
    agents = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")

    prompt_scratch, agents_scratch = (
        {path for path in _data_paths(text) if "scratch" in path}
        for text in (load_task_prompt(PROMPT), agents)
    )

    assert prompt_scratch == agents_scratch == {SCRATCH_DIRECTORY}


@pytest.mark.parametrize(
    "kept",
    [
        "Keep every test that exists",
        "Each reply of yours has an output cap",
        "The shell refuses any other program",
        "Tick each task of your group",
    ],
)
def test_the_prompt_keeps_the_facts_of_the_runner(kept: str) -> None:
    assert kept in load_task_prompt(PROMPT)


def test_the_instructions_of_the_runner_win_over_a_rule_that_conflicts_with_them() -> None:
    """AGENTS.md describes the work of a person and of the job: branches, commits, pull requests,
    the archive and the full check. The agent does none of it, so the prompt says which text wins."""
    prompt = load_task_prompt(PROMPT)

    assert "these instructions win and you ignore that rule" in prompt


def test_the_prompt_lists_the_work_that_the_job_does_in_place_of_the_agent() -> None:
    prompt = load_task_prompt(PROMPT)

    assert [
        work
        for work in (
            "commit",
            "push",
            "archive",
            "pull request",
            "devops roadmap return",
            "devops ci",
        )
        if work not in prompt.split("Follow them")[1].split("Work in this order")[0]
    ] == []
