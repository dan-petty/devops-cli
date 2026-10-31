"""The contract of the scanner fake: it answers each scanner adapter as the real scanner did
(#1666, #1982, ADR 0007).

Each run in `tests/fixtures/scanner_runs/recorded_runs.json` is the real tool's, at the version
`tools.lock` pins, started through its adapter as a review starts it (Semgrep's on 2026-10-24,
Gitleaks' on 2026-10-25, the others' on 2026-10-20), over one file holding `print("hello")`. Semgrep's recording ran
offline, with the rule file `_SEMGREP_RULES` in place of the registry's `p/default`, which a
recording cannot fetch. Each case starts the adapter that way again, through the default tool
executor, which `ScannerFake` answers. It checks that the adapter made the recorded command and
read the recorded run as it read the real one: a scan that ran and found nothing. Another checks
each recording's version against the lock. Where a case fails, the recording no longer stands for
the real tool: record the run again with the real tool at its locked version, as the fake's
docstring says. The last cases hold the fake to its install: the recorded scanners are on PATH,
the fake answers them and no other tool, and it answers the canary run of each tool with the
recorded canary output, through the default executor and as the executor that a test gives."""

from __future__ import annotations

import json
import shutil
import tomllib
from collections.abc import Callable
from pathlib import Path

import pytest
from packaging.requirements import Requirement

from devops_cli.review.canary import run_tool_canary
from devops_cli.review.rules_pack import RULE_PACK_DIR
from devops_cli.security.bandit import run_bandit_scan
from devops_cli.security.base import ScanOutcome
from devops_cli.security.gitleaks import run_gitleaks_scan
from devops_cli.security.osv_scanner import run_osv_scan
from devops_cli.security.registry import ScannerRegistry
from devops_cli.security.semgrep import run_semgrep_scan
from devops_cli.security.tool_executor import DirectToolExecutor, ToolRequest
from devops_cli.tools_lock import load_tools_lock
from tests.support.fakes.git import GitFake
from tests.support.fakes.process import ProcessAnswer
from tests.support.fakes.scanners import ScannerFake, ScannerRun
from tests.support.fakes.tool_executor import FAKE_EXECUTOR, ToolAnswer
from tests.support.paths import FIXTURES, REPO_ROOT

ReviewScan = Callable[[Path, Path], ScanOutcome]

# The one rule of the rule file Semgrep's recording ran with; it matches nothing in the scanned file.
_SEMGREP_RULES = """rules:
  - id: eval-of-input
    languages: [python]
    severity: ERROR
    message: eval of input
    pattern: eval(input())
"""


def _review_semgrep_scan(target: Path, tree: Path) -> ScanOutcome:
    """Semgrep as a review's scanner stage starts it, with a rule file in `tree` as its config."""
    rules = tree / "rules.yaml"
    rules.write_text(_SEMGREP_RULES, encoding="utf-8")
    return run_semgrep_scan([target], config=str(rules), reviewed_tree=tree)


# Each adapter as a review's scanner stage starts it (`devops_cli.ai.review.pipeline`).
REVIEW_SCANS: dict[str, ReviewScan] = {
    "semgrep": _review_semgrep_scan,
    "gitleaks": lambda target, tree: run_gitleaks_scan([target], ignore_tests=True, isolated=True),
    "bandit": lambda target, tree: run_bandit_scan([target], isolated=True, tree=tree),
    "osv-scanner": lambda target, tree: run_osv_scan([target], tree=tree, isolated=True),
}


@pytest.mark.parametrize("tool", sorted(REVIEW_SCANS))
def test_an_adapter_makes_the_recorded_command_and_reads_the_recorded_run(
    tool: str, scanner_fake: ScannerFake, tmp_path: Path
) -> None:
    """The adapter starts the recorded command and reads the recorded run as a clean scan."""
    tree = (tmp_path / "tree").resolve()
    tree.mkdir()
    target = tree / "app.py"
    target.write_text('print("hello")\n', encoding="utf-8")

    outcome = REVIEW_SCANS[tool](target, tree)

    [run] = scanner_fake.runs
    recorded = [
        word.format(tree=tree, workdir=run.cwd, rule_pack=RULE_PACK_DIR)
        for word in scanner_fake.recorded[tool].argv
    ]
    assert (run.argv, outcome.status, outcome.findings) == (recorded, "ran", [])


def test_each_recording_is_of_the_version_the_tools_lock_pins(scanner_fake: ScannerFake) -> None:
    """A tool bumped in the lock is recorded again."""
    locked = load_tools_lock().tools()

    assert {tool: run.version for tool, run in scanner_fake.recorded.items()} == {
        tool: locked[tool].version for tool in scanner_fake.recorded
    }


def test_each_run_with_findings_is_of_the_version_the_tools_lock_pins() -> None:
    """A tool bumped in the lock has its run with findings recorded again (#2214). The images pin
    uv, and the tools lock does not (#2106), so the test does not compare the run of uv."""
    runs = json.loads((FIXTURES / "scanner_runs" / "runs_with_findings.json").read_text())
    locked = load_tools_lock().tools()
    pinned_by_the_lock = [tool for tool in runs if tool != "uv"]

    assert {tool: runs[tool]["version"] for tool in pinned_by_the_lock} == {
        tool: locked[tool].version for tool in pinned_by_the_lock
    }


def test_a_registry_scan_whose_pinned_program_is_missing_runs_no_built_in_patterns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A scanner whose program `tools.lock` pins runs that program, and with no program on PATH
    its scan gives no result: no hand-written check stands in for the pinned tool (#2214)."""
    pinned = {command for tool in load_tools_lock().tools().values() for command in tool.commands}
    registry = ScannerRegistry(auto_load_defaults=True)
    names = [
        name
        for name in registry.list_scanners()
        if (scanner := registry.get(name)) is not None and scanner.binary_name in pinned
    ]
    no_programs = tmp_path / "no-programs"
    no_programs.mkdir()
    monkeypatch.setenv("PATH", str(no_programs))
    (tmp_path / "deploy.yaml").write_text("apiVersion: v1\nkind: ConfigMap\n", encoding="utf-8")

    outcomes = registry.scan_all(tmp_path, names=names)

    assert "kubeconform" in outcomes
    assert [
        name for name, outcome in outcomes.items() if outcome.status == "built-in patterns"
    ] == []


def test_every_scanner_of_the_registry_has_a_pinned_program() -> None:
    """A scanner's program is a command of a tool in `tools.lock`, or a dev dependency that
    `pyproject.toml` pins, so no scanner of the registry names a program that nothing installs
    at a known version (#2427)."""
    pinned = {command for tool in load_tools_lock().tools().values() for command in tool.commands}
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dev_pins = {Requirement(pin).name for pin in pyproject["dependency-groups"]["dev"]}
    registry = ScannerRegistry(auto_load_defaults=True)

    unpinned = [
        name
        for name in registry.list_scanners()
        if (scanner := registry.get(name)) is not None
        and scanner.binary_name not in pinned | dev_pins
    ]

    assert unpinned == []


def test_the_fake_finds_and_answers_only_the_recorded_scanners(
    scanner_fake: ScannerFake, tmp_path: Path, git_fake: GitFake
) -> None:
    """`shutil.which` finds each recorded scanner under `bin_dir`, the default executor hands a
    request for a recorded scanner to the fake, and it starts any other tool, such as git."""
    git_fake.answer(lambda c: True, ProcessAnswer(stdout="git version 2.43.0\n"))
    tree = (tmp_path / "tree").resolve()
    tree.mkdir()
    gitleaks = ToolRequest(tool="gitleaks", arguments=("version",), workdir=tree, targets=(tree,))
    git = gitleaks.model_copy(update={"tool": "git", "arguments": ("--version",)})

    found = {tool: shutil.which(tool) for tool in scanner_fake.recorded}
    answered = DirectToolExecutor().run(gitleaks)
    started = DirectToolExecutor().run(git)

    assert (
        found,
        (answered.exit_code, answered.stderr, answered.run.executor),
        started.stdout.startswith("git version"),
        scanner_fake.runs,
    ) == (
        {tool: str(scanner_fake.bin_dir / tool) for tool in scanner_fake.recorded},
        (0, scanner_fake.recorded["gitleaks"].stderr, FAKE_EXECUTOR),
        True,
        [ScannerRun(["gitleaks", "version"], str(tree))],
    )


# The tools that have a canary and that the fake can answer: Semgrep and Bandit, which it holds a
# recording of, and kube-linter and Pluto, which a test can script. Gitleaks and osv-scanner have no
# canary.
@pytest.mark.parametrize("given", [False, True], ids=["default-executor", "given-executor"])
@pytest.mark.parametrize("tool", ["semgrep", "bandit", "kube-linter", "pluto"])
def test_a_canary_run_gets_the_recorded_canary_answer_and_not_the_answer_of_the_fake(
    tool: str, given: bool, scanner_fake: ScannerFake
) -> None:
    """A review runs the canary of each tool on its tool executor before its scans: the default
    executor, or the fake that a test gives the orchestrator (#1978, #2098). The fake holds an
    answer for the tool, an empty run that the canary does not pass on. It answers a run in a
    canary working directory with the recorded canary output, so the canary passes, and it keeps
    the canary run apart from the runs of the scans."""
    scanner_fake.script(tool, ToolAnswer())

    result = run_tool_canary(tool, use_cache=False, tool_executor=scanner_fake if given else None)

    assert (
        result.passed,
        scanner_fake.runs,
        [request.tool for request in scanner_fake.canaries.requests],
    ) == (True, [], [tool])
