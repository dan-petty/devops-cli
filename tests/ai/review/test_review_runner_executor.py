"""A review in the pod of a runner Job starts its scanners with the direct executor (#3827).

The pod's `RuntimeDefault` seccomp profile refuses the `unshare` that the bubblewrap sandbox of a
review needs, so a review there runs its tools as children of the review, and the pod is the
isolation boundary. Outside the pod, a review keeps the sandbox: the setting
`roadmap.implement.in_runner` is the only switch, and only the runner pod sets it.

These cases fake the process edge with `process_fake`, so no scanner and no sandbox starts. The
answer of a scanner's canary is the output that the pinned tool printed for it, as
`tests/fixtures/review_canary/recorded_outputs.json` holds it, so each canary passes and the
finding of each scan is admitted.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path

import pytest

from devops_cli.ai.review.flags import resolve_stage_flags
from devops_cli.ai.review.runner import ReviewClients, execute_review_workflow
from devops_cli.ai.review_schema import ReviewResult
from devops_cli.config.constants import CONST_CANARY_WORKDIR_PREFIX
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.paths import FIXTURES

_ANALYZERS = ("bandit", "gitleaks", "semgrep")
# The report of a scan, with no group analysis, so no model reads the admitted findings.
_NO_GROUP_ANALYSIS = resolve_stage_flags(no_group_analysis=True)


def _recorded_canary_outputs() -> dict[str, str]:
    """The output that the pinned tool printed for its canary, by the tool's name."""
    recorded = FIXTURES / "review_canary" / "recorded_outputs.json"
    entries = json.loads(recorded.read_text(encoding="utf-8"))
    return {
        tool: output if isinstance(output := entry.get("output"), str) else json.dumps(output)
        for tool, entry in entries.items()
    }


_CANARY_OUTPUTS = _recorded_canary_outputs()


@pytest.fixture
def bwrap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A stand-in for bubblewrap first on PATH. Nothing starts it: `process_fake` answers it."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stand_in = bin_dir / "bwrap"
    stand_in.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
    stand_in.chmod(0o755)
    monkeypatch.setenv("PATH", os.pathsep.join([str(bin_dir), os.environ.get("PATH", "")]))
    return stand_in


@pytest.fixture
def review_tree(tmp_path: Path) -> Path:
    """A tree outside any checkout, with one Python file to review."""
    root = (tmp_path / "tree").resolve()
    root.mkdir()
    (root / "app.py").write_text('print("hello")\n', encoding="utf-8")
    return root


def _bandit_report(tree: Path) -> str:
    """Bandit's JSON report with one HIGH finding on line 1 of `tree`'s Python file."""
    return json.dumps(
        {
            "results": [
                {
                    "filename": str(tree / "app.py"),
                    "line_number": 1,
                    "test_id": "B602",
                    "test_name": "subprocess_popen_with_shell_equals_true",
                    "issue_text": "subprocess shell=True",
                    "issue_severity": "HIGH",
                    "issue_confidence": "HIGH",
                }
            ],
            "errors": [],
        }
    )


def _gitleaks_report(tree: Path) -> str:
    """Gitleaks' JSON report with one leaked secret in `tree`'s Python file."""
    return json.dumps(
        [
            {
                "RuleID": "github-pat",
                "Description": "GitHub Personal Access Token",
                "File": str(tree / "app.py"),
                "StartLine": 1,
                "EndLine": 1,
                "Match": "REDACTED",
                "Secret": "REDACTED",
            }
        ]
    )


def _semgrep_report(tree: Path) -> str:
    """Semgrep's JSON report with one result in `tree`'s Python file."""
    return json.dumps(
        {
            "version": "1.179.0",
            "results": [
                {
                    "check_id": "example.lang.security.first.first",
                    "path": str(tree / "app.py"),
                    "start": {"line": 1, "col": 1},
                    "end": {"line": 1, "col": 6},
                    "extra": {"message": "first", "severity": "ERROR"},
                }
            ],
            "errors": [],
            "paths": {"scanned": []},
        }
    )


def _scan_answer(tool: str, stdout: str) -> Callable[[ProcessCall], ProcessAnswer]:
    """The answer of `tool`: its canary output in the canary's working directory, else `stdout`."""

    def answer(call: ProcessCall) -> ProcessAnswer:
        if call.cwd is not None and call.cwd.name.startswith(CONST_CANARY_WORKDIR_PREFIX):
            return ProcessAnswer(stdout=_CANARY_OUTPUTS[tool])
        return ProcessAnswer(stdout=stdout)

    return answer


def _answer_analyzers(process_fake: ProcessFake, tree: Path) -> None:
    """Answer Bandit, Gitleaks and Semgrep with a report that holds a finding each."""
    for tool, stdout in (
        ("bandit", _bandit_report(tree)),
        ("gitleaks", _gitleaks_report(tree)),
        ("semgrep", _semgrep_report(tree)),
    ):
        process_fake.answer(
            lambda call, name=tool: Path(call.argv[0]).name == name,
            _scan_answer(tool, stdout),
        )


def _tool_commands(process_fake: ProcessFake) -> list[tuple[str, ...]]:
    """Each command that the fake answered, less the commands of git."""
    return [call.argv for call in process_fake.calls if Path(call.argv[0]).name != "git"]


def _confined_program(argv: tuple[str, ...]) -> str:
    """The file name of the program that a sandbox command starts. The options of bubblewrap end
    with `--`, and the options of `prlimit` end with the next `--`."""
    under_prlimit = argv[argv.index("--") + 1 :]
    return Path(under_prlimit[under_prlimit.index("--") + 1]).name


def _review(tree: Path, *, in_runner: bool) -> list[ReviewResult | str]:
    """A review of `tree`'s Python file, as the command runs it with `in_runner`."""
    return execute_review_workflow(
        [f"### File: app.py\n{(tree / 'app.py').read_text(encoding='utf-8')}"],
        "Path review",
        False,
        ReviewClients(),
        target_type="path",
        target_ref=str(tree),
        target_dir=tree,
        stage_flags=_NO_GROUP_ANALYSIS,
        in_runner=in_runner,
    )


def test_a_review_in_the_runner_pod_starts_its_scanners_with_the_direct_executor(
    review_tree: Path, process_fake: ProcessFake
) -> None:
    """The review gets the runner flag, so each scanner starts as a child of the review by
    `DirectToolExecutor`: no command starts bubblewrap, and the report holds the finding of each
    scanner."""
    _answer_analyzers(process_fake, review_tree)

    results = _review(review_tree, in_runner=True)

    commands = _tool_commands(process_fake)
    findings = [finding for result in results for finding in getattr(result, "findings", [])]
    assert (
        {Path(argv[0]).name for argv in commands} & set(_ANALYZERS),
        "bwrap" in {Path(argv[0]).name for argv in commands},
        {finding.producer for finding in findings} & set(_ANALYZERS),
    ) == (set(_ANALYZERS), False, set(_ANALYZERS))


def test_a_review_outside_the_runner_pod_keeps_the_sandbox(
    review_tree: Path, bwrap: Path, process_fake: ProcessFake
) -> None:
    """The default keeps the sandbox: each scanner runs inside bubblewrap, as it does on a
    workstation and in the Service pod (#2096, decision 1 of #772)."""
    _answer_analyzers(process_fake, review_tree)

    _review(review_tree, in_runner=False)

    commands = _tool_commands(process_fake)
    assert (
        {argv[0] for argv in commands},
        {"bandit", "gitleaks", "semgrep"} <= {_confined_program(argv) for argv in commands},
    ) == ({str(bwrap)}, True)
