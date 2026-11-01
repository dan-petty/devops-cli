"""The prompt of the implement step tells the agent where its scratch files go (#3006): the step
commits every file in the checkout, so a scratch file outside the ignored directory would reach
the pull request."""

from __future__ import annotations

from devops_cli.ai.task_loader import load_task_prompt

PROMPT = "roadmap_implement_step.md"
SCRATCH_DIRECTORY = ".data/agent/scratch/"


def test_the_prompt_names_the_ignored_scratch_directory() -> None:
    prompt = load_task_prompt(PROMPT)

    assert SCRATCH_DIRECTORY in prompt


def test_the_prompt_keeps_scratch_files_out_of_the_checkout_root() -> None:
    prompt = load_task_prompt(PROMPT)

    assert "Put no scratch file in the checkout root" in prompt
