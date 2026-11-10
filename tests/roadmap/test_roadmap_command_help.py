"""The help of the long roadmap commands is a short summary that names the page of its job (#3188).

`devops roadmap --help` lists each command with the start of its help, so a long help hides the
list. The long description of each job lives in `docs/roadmap/<command>.md`.
"""

from __future__ import annotations

import re

import pytest

from devops_cli.lang import HELP
from tests.support.paths import REPO_ROOT

MAX_SENTENCES = 3

COMMANDS = {
    "intake": HELP.roadmap.intake,
    "refine": HELP.roadmap.refine,
    "alternatives": HELP.roadmap.alternatives,
    "stage": HELP.roadmap.stage,
    "implement": HELP.roadmap.implement,
    "inbox": HELP.roadmap.inbox,
    "consolidate": HELP.roadmap.consolidate,
}


def _sentences(text: str) -> list[str]:
    return [part for part in re.split(r"(?<=\.)\s+", text.strip()) if part]


@pytest.mark.parametrize("command", COMMANDS)
def test_the_help_of_a_job_command_is_a_summary_of_at_most_three_sentences(command: str) -> None:
    assert len(_sentences(COMMANDS[command])) <= MAX_SENTENCES


@pytest.mark.parametrize("command", COMMANDS)
def test_the_help_of_a_job_command_names_a_page_that_exists(command: str) -> None:
    page = f"docs/roadmap/{command}.md"

    assert page in COMMANDS[command]
    assert (REPO_ROOT / page).is_file()


def test_the_help_and_the_page_of_stage_plan_say_one_local_file_and_no_github_write() -> None:
    page = (REPO_ROOT / "docs/roadmap/stage.md").read_text(encoding="utf-8")
    row = next(line for line in page.splitlines() if line.startswith("| `--plan`"))

    for text in (HELP.roadmap.stage_plan, row):
        assert "one local file" in text
        assert "no GitHub write" in text
        assert "writes nothing" not in text
        assert "write nothing" not in text
