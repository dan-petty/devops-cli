"""The trace gate reads the subject and the object of a read word (#4314, #4495).

A sentence that says what code, the plan, a group or the probe does ("it reads
`.github/labels.yml`", "this plan reads `x.py` in group 2") is no claim that the run read a file. A
claim of the run or of the author ("I read", "the run read", "`read_file` of", "`x.py` was read")
still is, and the gate judges the path that the read takes as its object.
"""

from __future__ import annotations

from typing import Any

import pytest

from devops_cli.roadmap.agent_run import TraceFacts
from devops_cli.roadmap.stage.stage_change import StageProposal, check_proposal
from devops_cli.roadmap.stage.stage_paths import StagedTree
from devops_cli.roadmap.tools import HOLDER_STAGE_EXTENDED, tool_names
from tests.support.builders import make_stage_proposal

TREE = StagedTree(["src/devops_cli/sample.py", ".github/labels.yml"])
NO_CALLS = TraceFacts()


def _problems(sentence: str, trace: TraceFacts | None = NO_CALLS) -> list[str]:
    plan: StageProposal = make_stage_proposal(feasibility=[sentence])
    # An empty registry keeps the registry gate from parsing each test file of the repository.
    keywords: dict[str, Any] = {"trace": trace, "registry": []}
    return check_proposal(plan, ["comment-thread"], TREE, **keywords)


@pytest.mark.parametrize(
    "sentence",
    [
        "Precondition of `declared_labels(self.store, ref=None)`: a client of the GitHub "
        "service, because it reads `.github/labels.yml` of the default branch.",
        "The helper is the one which reads `.github/labels.yml` of the default branch.",
        "The function `declared_labels` reads `.github/labels.yml` of the default branch.",
        "The check `scope_check`, reading `.github/labels.yml`, needs a client.",
        "It is a client of the GitHub service, because it is reading `.github/labels.yml`.",
    ],
)
def test_code_that_reads_a_file_is_no_claim_that_the_run_read_it(sentence: str) -> None:
    assert _problems(sentence) == []


@pytest.mark.parametrize(
    "sentence",
    [
        "I read `src/devops_cli/sample.py` and found the function.",
        "The run read `src/devops_cli/sample.py` and found the function.",
        "The run reads `src/devops_cli/sample.py` and finds the function.",
        "After reading `src/devops_cli/sample.py`, the plan names the function.",
        "The run called `read_file` on `src/devops_cli/sample.py`.",
        "The function `declared_labels` is there, and I read `src/devops_cli/sample.py`.",
    ],
)
def test_a_claim_of_the_run_with_no_call_for_the_path_is_still_refused(sentence: str) -> None:
    problems = _problems(sentence)

    assert len(problems) == 1
    assert "did not read" in problems[0]


def test_a_claim_of_the_run_is_true_when_the_run_read_the_path() -> None:
    trace = TraceFacts(
        tools=frozenset({"read_file"}), paths=frozenset({"src/devops_cli/sample.py"})
    )

    assert _problems("I read `src/devops_cli/sample.py` and found it.", trace) == []


# The trace gate parses the subject and the object of each read word (#4495). The trace holds every
# tool of the toolbox and the path `src/devops_cli/sample.py`, so only a claim of another path fails.
ALL_TOOLS = TraceFacts(
    tools=frozenset(tool_names(HOLDER_STAGE_EXTENDED)),
    paths=frozenset({"src/devops_cli/sample.py"}),
)


def _read_refusals(sentence: str) -> list[str]:
    """The refusals of the trace gate for a read claim in `sentence`: the other gates judge paths
    that this tree does not hold."""
    return [p for p in _problems(sentence, ALL_TOOLS) if "but the run did not read it" in p]


@pytest.mark.parametrize(
    "sentence",
    [
        # The plan, a group, a test case, the probe or a line of a file is the subject: no claim of
        # the run. The first four are refused records of the stage job (#4442, #3388, #3389).
        "This plan reads `tests/ai/client/test_ai_client_finish_reasons.py` in group 2.",
        "`search_code` for `devops_cli.lang.en.messages` shows the import line "
        "`tests/roadmap/implement/test_roadmap_implement_amend.py:5:from x import y`, so the "
        "group that changes the catalog reads that test.",
        "`search_code` of `### Registry places` gave "
        "`tests/roadmap/stage/test_roadmap_stage_plan.py:553:assert x`, so the new case reads "
        "the request context in that test module.",
        "The probe of the stream type reads, word for word: The path "
        "`src/devops_cli/ai/client/network.py` is a file of the staging commit.",
        "`search_code` for `get_pull_files` showed the other readers at "
        "`src/devops_cli/ai/review/runner.py:470`, which keep the pulls files read.",
        "Groups 1 and 3 read `src/devops_cli/other.py` and keep it.",
        "The code that reads `src/devops_cli/other.py` is `load_config`.",
        "The replay reads `src/devops_cli/other.py` and runs no git.",
        "Line 20 of `docs/adr/0008-workflows.md` reads `Temporal: rejected`.",
        "All checks ran on `origin/main` with Ruff 0.16.8.",
        # `read-only` is no read word (#3049).
        "`k8s/devops/cronjob-runner.yaml` runs the pod as user 1000 with a read-only root.",
        # The object of the read is no path, and the path after it is in another clause (#3453).
        "`read_file` of that prompt at lines 24 and 26 shows the key list, and `search_code` "
        "with `Adds:` returned one hit in `src/devops_cli/commands/tf.py`.",
    ],
)
def test_a_read_word_whose_subject_or_object_is_not_a_read_of_the_run_is_no_claim(
    sentence: str,
) -> None:
    assert _read_refusals(sentence) == []


@pytest.mark.parametrize(
    ("sentence", "path"),
    [
        ("I read `src/missing.py` and found the function.", "src/missing.py"),
        ("We read `src/missing.py` first.", "src/missing.py"),
        ("The plan run read `src/missing.py` and found it.", "src/missing.py"),
        ("Read `src/missing.py` for the seam.", "src/missing.py"),
        ("Reading `src/missing.py` shows the seam.", "src/missing.py"),
        ("This is confirmed by reading `src/missing.py` at the base.", "src/missing.py"),
        ("`src/missing.py` was read on the base.", "src/missing.py"),
        ("The same read shows `src/missing.py:def load`, which loads it.", "src/missing.py"),
        ("The read of lines 1 to 9 shows `src/missing.py:3:x = 1`.", "src/missing.py"),
        ("`read_file` of `src/missing.py` line 478 shows the reader.", "src/missing.py"),
        ("The code is `load`, which the planner read in `src/missing.py`.", "src/missing.py"),
        # Each read claim of a sentence is judged, not only the first path of the sentence.
        (
            "I read `src/devops_cli/sample.py`, and the same read of `src/missing.py` shows it.",
            "src/missing.py",
        ),
        ("This plan reads `src/other.py`, and I read `src/missing.py`.", "src/missing.py"),
        # A read whose object is a pronoun reads the last path before it.
        (
            "`file_symbols` of `src/missing.py` lists `load`, and `read_file` of it shows it.",
            "src/missing.py",
        ),
        ("The issue cites `src/missing.py`, and `read_file` shows that line.", "src/missing.py"),
    ],
)
def test_a_read_claim_of_the_run_with_no_read_of_its_object_is_refused(
    sentence: str, path: str
) -> None:
    problems = _read_refusals(sentence)

    assert len(problems) == 1
    assert f"`{path}` was read" in problems[0]
