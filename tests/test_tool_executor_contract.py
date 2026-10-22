"""The contract of the review-tool executor: the real sandbox executor and the fake answer a
request the same way (#772, ADR 0007).

A review tool starts through a `ToolExecutor`. The real executor builds a bubblewrap command and
starts it through `run_subprocess`. `ToolExecutorFake` starts nothing. Each shared case runs over
both, with a stand-in for the tool on disk. The stand-in is a shell script named after a tool that
`tools.lock` pins, and a test puts it first on PATH. The real side carries the `bwrap` mark, so
tests skip it where bubblewrap is missing.

The cases after the shared ones hold the real executor to what it promises. They check the
confinement that it asks bubblewrap for, and the limits that the tool runs under. They also check
that a tool which runs out of time leaves no process behind.
"""

from __future__ import annotations

import hashlib
import os
import re
import resource
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

from devops_cli.config.constants import (
    CONST_ERROR_CODE_SANDBOX,
    CONST_ERROR_CODE_SANDBOX_VALIDATION,
    CONST_SANDBOX_TIMEOUT_EXIT_CODE,
)
from devops_cli.config.defaults import DEFAULT_REPOMAP_MAX_FILE_SIZE_BYTES
from devops_cli.exceptions.sandbox import SandboxError, SandboxValidationError
from devops_cli.sandbox.host import DEFAULT_HOST_SANDBOX_POLICY, HostSandbox
from devops_cli.security.tool_executor import (
    SandboxToolExecutor,
    ToolExecutor,
    ToolLimits,
    ToolRequest,
    ToolResult,
    ToolRun,
)
from devops_cli.tools_lock import load_tools_lock
from tests.support.fakes.tool_executor import ToolAnswer, ToolExecutorFake
from tests.support.waits import wait_until

# A tool that `tools.lock` pins, so the run records the locked version; the stand-in is not it.
_TOOL = "helm"
_SANDBOX_ARGS = ("--unshare-all", "--new-session", "--die-with-parent", "--clearenv")
# The sandbox's private tmpfs, which is also the HOME of the tool.
_PRIVATE_TMP = next(iter(DEFAULT_HOST_SANDBOX_POLICY.tmpfs))

# What the stand-in does for its first argument. `scan` ends with a warning and exit code 3, as a
# scanner that found something does. `probe` reports what the sandbox gave it. `hang` starts a
# child with its target in the command line, and waits on it. A scan of the processes of the host
# for the target then finds the child for as long as the tree runs.
_STAND_IN = """#!/bin/sh
case "$1" in
scan)
  echo "scanned: $2"
  echo "warning" >&2
  exit 3
  ;;
probe)
  grep -E '^Max (cpu time|address space|processes)' /proc/self/limits
  echo "GOMEMLIMIT=$GOMEMLIMIT"
  echo "HOME=$HOME"
  echo "SECRET=$DEVOPS_TOOL_TEST_SECRET"
  echo "INTERFACES=$(tail -n +3 /proc/net/dev | cut -d: -f1 | tr -d ' ' | tr '\\n' ',')"
  for input in "$2/app.py" "$3"; do
    if [ ! -r "$input" ]; then access=missing
    elif (: >> "$input") 2>/dev/null; then access=writable
    else access=read-only
    fi
    echo "INPUT $input=$access"
  done
  ;;
hang)
  echo started
  sh -c 'sleep 4242' "$2" &
  wait
  ;;
esac
"""


@dataclass(frozen=True)
class Scenario:
    """A git tree to review, a stand-in for the tool, and the files a request names."""

    tree: Path
    tools_dir: Path
    stand_in: Path
    config_file: Path
    ruleset_file: Path
    commit: str

    @property
    def target(self) -> Path:
        """The one directory of the tree a request scans."""
        return self.tree / "src"

    @property
    def binary_sha256(self) -> str:
        """The digest of the stand-in's bytes, which the run must record for the tool."""
        return hashlib.sha256(self.stand_in.read_bytes()).hexdigest()

    @property
    def locked_version(self) -> str:
        """The version `tools.lock` pins for the tool."""
        return load_tools_lock().tools()[_TOOL].version

    def request(self, *arguments: str, limits: ToolLimits | None = None) -> ToolRequest:
        """A request to run the stand-in over the tree's `src`, with the scenario's files."""
        return ToolRequest(
            tool=_TOOL,
            arguments=arguments or ("scan", "{targets}"),
            workdir=self.tree,
            targets=(self.target,),
            config_files=(self.config_file,),
            ruleset_files=(self.ruleset_file,),
            read_only_binds=(self.tools_dir,),
            limits=limits or ToolLimits(),
        )


@pytest.fixture
def scenario(tmp_path: Path, git: Callable[..., None], monkeypatch: pytest.MonkeyPatch) -> Scenario:
    """A one-commit git tree with a stand-in for the tool first on PATH."""
    tree = tmp_path / "tree"
    (tree / "src").mkdir(parents=True)
    (tree / "src" / "app.py").write_text("print('hello')\n", encoding="utf-8")
    git(tree, "init", "--quiet")
    git(tree, "add", ".")
    git(tree, "commit", "--quiet", "-m", "first")
    commit = subprocess.run(
        ["git", "-C", str(tree), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()

    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    stand_in = tools_dir / _TOOL
    stand_in.write_text(_STAND_IN, encoding="utf-8")
    stand_in.chmod(0o755)
    monkeypatch.setenv("PATH", os.pathsep.join([str(tools_dir), os.environ["PATH"]]))

    rules = tmp_path / "rules"
    rules.mkdir()
    config_file = rules / "tool.yaml"
    ruleset_file = rules / "ruleset.json"
    config_file.write_text("strict: true\n", encoding="utf-8")
    ruleset_file.write_text('{"version": "2026-10-22"}\n', encoding="utf-8")
    return Scenario(tree, tools_dir, stand_in, config_file, ruleset_file, commit)


@pytest.fixture(params=["fake", pytest.param("sandbox", marks=pytest.mark.bwrap)])
def executor(request: pytest.FixtureRequest, scenario: Scenario) -> ToolExecutor:
    """The fake, scripted as the stand-in answers `scan`, then the real sandbox executor."""
    if request.param == "sandbox":
        return SandboxToolExecutor()
    fake = ToolExecutorFake()
    fake.script(
        _TOOL,
        ToolAnswer(
            exit_code=3,
            stdout=f"scanned: {scenario.target}\n",
            stderr="warning\n",
            version=scenario.locked_version,
            binary_sha256=scenario.binary_sha256,
        ),
    )
    return fake


def test_a_run_answers_the_exit_code_and_the_output_of_the_tool(
    executor: ToolExecutor, scenario: Scenario
) -> None:
    """A tool that exits with 3 and warns on stderr is answered as it ended, not as a failure."""
    result = executor.run(scenario.request())

    assert (result.exit_code, result.stdout, result.stderr, result.timed_out) == (
        3,
        f"scanned: {scenario.target}\n",
        "warning\n",
        False,
    )


def test_a_run_records_the_tool_the_files_it_read_and_the_commit(
    executor: ToolExecutor, scenario: Scenario
) -> None:
    """The record names the tool as `tools.lock` pins it, the digest of the binary that ran, the
    argument template, and the commit of the tree."""
    run = executor.run(scenario.request()).run

    assert (run.tool, run.version, run.binary_sha256, run.argv_template, run.commit) == (
        _TOOL,
        scenario.locked_version,
        scenario.binary_sha256,
        (_TOOL, "scan", "{targets}"),
        scenario.commit,
    )


def test_a_run_records_a_digest_of_each_file_and_target_it_names(
    executor: ToolExecutor, scenario: Scenario
) -> None:
    """The config, the ruleset and the targets each have a digest of their own, none empty."""
    run = executor.run(scenario.request()).run

    digests = {run.config_digest, run.ruleset_digest, run.targets_digest}
    assert (len(digests), all(re.fullmatch(r"[0-9a-f]{16}", digest) for digest in digests)) == (
        3,
        True,
    )


def test_each_digest_follows_the_content_it_names(
    executor: ToolExecutor, scenario: Scenario
) -> None:
    """Changing the config changes the config digest alone, the ruleset the ruleset digest alone,
    and another target the targets digest alone."""
    before = executor.run(scenario.request()).run
    scenario.config_file.write_text("strict: false\n", encoding="utf-8")
    after_config = executor.run(scenario.request()).run
    scenario.ruleset_file.write_text('{"version": "2026-10-23"}\n', encoding="utf-8")
    after_ruleset = executor.run(scenario.request()).run
    other = scenario.request()
    other = other.model_copy(update={"targets": (scenario.tree / "src" / "app.py",)})
    after_target = executor.run(other).run

    def changed(run: ToolRun) -> set[str]:
        return {
            name
            for name in ("config_digest", "ruleset_digest", "targets_digest")
            if getattr(run, name) != getattr(before, name)
        }

    assert (
        changed(after_config),
        changed(after_ruleset) - changed(after_config),
        changed(after_target) - changed(after_ruleset),
    ) == ({"config_digest"}, {"ruleset_digest"}, {"targets_digest"})


def test_a_tree_outside_any_repository_records_no_commit(
    executor: ToolExecutor, scenario: Scenario, tmp_path: Path
) -> None:
    """A directory that is no git checkout has no commit, so the record holds none."""
    plain = tmp_path / "plain"
    (plain / "src").mkdir(parents=True)
    request = scenario.request().model_copy(update={"workdir": plain, "targets": (plain / "src",)})

    assert executor.run(request).run.commit is None


def _directory_outside_the_tree(scenario: Scenario) -> Path:
    """A directory beside the tree, named by its path."""
    return scenario.tools_dir


def _link_inside_the_tree_to_a_directory_outside_it(scenario: Scenario) -> Path:
    """A link inside the tree whose target is a directory beside the tree."""
    link = scenario.target / "link"
    link.symlink_to(scenario.tools_dir, target_is_directory=True)
    return link


def _path_that_climbs_out_through_the_tree(scenario: Scenario) -> Path:
    """An absolute path that starts in the tree and climbs out of it with `..`."""
    return scenario.target / ".." / ".." / scenario.tools_dir.name


def _relative_path_that_climbs_out(scenario: Scenario) -> Path:
    """A path relative to the tree that climbs out of it with `..`."""
    return Path("..") / scenario.tools_dir.name


def _directory_whose_name_starts_with_the_tree_name(scenario: Scenario) -> Path:
    """A directory beside the tree whose path starts with the path of the tree."""
    sibling = scenario.tree.with_name(f"{scenario.tree.name}-other")
    sibling.mkdir()
    return sibling


@pytest.mark.parametrize(
    "escape",
    [
        _directory_outside_the_tree,
        _link_inside_the_tree_to_a_directory_outside_it,
        _path_that_climbs_out_through_the_tree,
        _relative_path_that_climbs_out,
        _directory_whose_name_starts_with_the_tree_name,
    ],
)
def test_a_target_that_leaves_the_tree_is_refused(
    executor: ToolExecutor, scenario: Scenario, escape: Callable[[Scenario], Path]
) -> None:
    """A tool never scans a path that leaves the tree it is confined to. This holds for a plain
    path, a link, a path that climbs out with `..`, and a path that only starts like the tree."""
    request = scenario.request().model_copy(update={"targets": (escape(scenario),)})

    with pytest.raises(SandboxValidationError) as refused:
        executor.run(request)

    assert (refused.value.error_code, refused.value.exit_code) == (
        CONST_ERROR_CODE_SANDBOX_VALIDATION,
        1,
    )


def test_a_tree_that_is_no_directory_is_refused(
    executor: ToolExecutor, scenario: Scenario, tmp_path: Path
) -> None:
    """A tree that does not exist has nothing to confine a tool to, so no tool runs."""
    missing = tmp_path / "no-such-tree"
    request = scenario.request().model_copy(
        update={"workdir": missing, "targets": (missing / "src",)}
    )

    with pytest.raises(SandboxValidationError, match="not a directory"):
        executor.run(request)


def test_a_target_that_is_a_link_to_a_place_in_the_tree_is_accepted(
    executor: ToolExecutor, scenario: Scenario
) -> None:
    """The control for the links that leave the tree: a link that stays in it runs, and the record
    names the place it points to."""
    link = scenario.tree / "link-to-src"
    link.symlink_to(scenario.target, target_is_directory=True)
    through_link = scenario.request().model_copy(update={"targets": (link,)})

    assert (
        executor.run(through_link).run.targets_digest
        == executor.run(scenario.request()).run.targets_digest
    )


def _missing_file(tmp_path: Path) -> Path:
    """A path with no file."""
    return tmp_path / "no-such-file.yaml"


def _device_file(tmp_path: Path) -> Path:
    """A file that is no regular file. Reading it ends at once, so a check that is missing shows
    as a test that fails and not as one that hangs."""
    return Path(os.devnull)


def _file_over_the_size_cap(tmp_path: Path) -> Path:
    """A sparse file one byte over the cap on the files a run reads into memory."""
    oversized = tmp_path / "oversized.json"
    with oversized.open("wb") as handle:
        handle.truncate(DEFAULT_REPOMAP_MAX_FILE_SIZE_BYTES + 1)
    return oversized


@pytest.mark.parametrize("field", ["config_files", "ruleset_files"])
@pytest.mark.parametrize("bad_file", [_missing_file, _device_file, _file_over_the_size_cap])
def test_a_file_that_cannot_be_digested_is_refused(
    executor: ToolExecutor,
    scenario: Scenario,
    tmp_path: Path,
    field: str,
    bad_file: Callable[[Path], Path],
) -> None:
    """A config or ruleset that is missing, is no regular file, or is too large to read into
    memory stops the run before it starts."""
    request = scenario.request().model_copy(update={field: (bad_file(tmp_path),)})

    with pytest.raises(SandboxValidationError, match="regular file"):
        executor.run(request)


def test_a_digest_names_the_content_of_its_files_not_their_paths_or_order(
    executor: ToolExecutor, scenario: Scenario, tmp_path: Path
) -> None:
    """The same rules in another checkout give the same digest, in whatever order they are named,
    and one more file gives another."""
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    moved = elsewhere / "renamed.json"
    moved.write_bytes(scenario.ruleset_file.read_bytes())
    extra = elsewhere / "extra.json"
    extra.write_text('{"extra": true}\n', encoding="utf-8")

    def ruleset_digest(*files: Path) -> str:
        request = scenario.request().model_copy(update={"ruleset_files": files})
        return executor.run(request).run.ruleset_digest

    in_place = ruleset_digest(scenario.ruleset_file)
    assert (
        ruleset_digest(moved) == in_place,
        ruleset_digest(scenario.ruleset_file, extra) == ruleset_digest(extra, moved),
        ruleset_digest(scenario.ruleset_file, extra) == in_place,
    ) == (True, True, False)


def _edit_a_tracked_file_in_the_target(scenario: Scenario) -> None:
    """Change the content of a file the commit holds."""
    (scenario.target / "app.py").write_text("print('changed')\n", encoding="utf-8")


def _add_a_file_to_the_target(scenario: Scenario) -> None:
    """Add a file the commit does not hold."""
    (scenario.target / "new.py").write_text("value = 1\n", encoding="utf-8")


def _add_a_file_outside_the_target(scenario: Scenario) -> None:
    """Add a file the commit does not hold, beside the target and not in it."""
    (scenario.tree / "README.md").write_text("outside\n", encoding="utf-8")


@pytest.mark.parametrize(
    ("change", "dirty"),
    [
        (_edit_a_tracked_file_in_the_target, True),
        (_add_a_file_to_the_target, True),
        (_add_a_file_outside_the_target, False),
    ],
)
def test_the_commit_is_marked_dirty_when_a_target_differs_from_it(
    executor: ToolExecutor,
    scenario: Scenario,
    change: Callable[[Scenario], None],
    dirty: bool,
) -> None:
    """A target that the commit does not describe is recorded as `<commit>-dirty`, as the source of
    devops-cli itself is. A change outside the targets leaves the commit as it is."""
    change(scenario)

    commit = executor.run(scenario.request()).run.commit

    assert commit == (f"{scenario.commit}-dirty" if dirty else scenario.commit)


def test_reading_the_commit_does_not_write_to_the_tree(
    executor: ToolExecutor, scenario: Scenario
) -> None:
    """A run reads the commit without refreshing the index of the checkout. Git rewrites an index
    whose file times are stale, and a review must leave the tree as it found it."""
    index = scenario.tree / ".git" / "index"
    os.utime(scenario.target / "app.py", (0, 0))
    before = index.read_bytes()

    executor.run(scenario.request())

    assert index.read_bytes() == before


def test_a_checkout_without_a_commit_records_no_commit(
    executor: ToolExecutor, scenario: Scenario, git: Callable[..., None], tmp_path: Path
) -> None:
    """A fresh checkout holds no commit yet, so the record holds none."""
    fresh = tmp_path / "fresh"
    (fresh / "src").mkdir(parents=True)
    git(fresh, "init", "--quiet")
    request = scenario.request().model_copy(update={"workdir": fresh, "targets": (fresh / "src",)})

    assert executor.run(request).run.commit is None


def test_a_checkout_that_git_cannot_read_is_refused_and_not_recorded_as_no_commit(
    executor: ToolExecutor, scenario: Scenario, tmp_path: Path
) -> None:
    """A tree with a `.git` that git cannot use, as one that git does not trust, is not a tree
    outside any checkout. A record that says there is no commit would be wrong."""
    broken = tmp_path / "broken"
    (broken / "src").mkdir(parents=True)
    (broken / ".git").mkdir()
    request = scenario.request().model_copy(
        update={"workdir": broken, "targets": (broken / "src",)}
    )

    with pytest.raises(SandboxError, match="commit") as refused:
        executor.run(request)

    assert refused.value.error_code == CONST_ERROR_CODE_SANDBOX


def test_the_fake_keeps_every_request_it_answered(
    tool_executor_fake: ToolExecutorFake, scenario: Scenario
) -> None:
    """A test reads back what the code under test asked of the tool."""
    request = scenario.request()

    tool_executor_fake.run(request)
    tool_executor_fake.run(request)

    assert tool_executor_fake.requests == [request, request]


def test_an_unscripted_tool_ends_in_success_with_no_output(
    tool_executor_fake: ToolExecutorFake, scenario: Scenario
) -> None:
    """The fake answers a tool nobody scripted with an empty success."""
    result = tool_executor_fake.run(scenario.request())

    assert (result.exit_code, result.stdout, result.stderr, result.timed_out) == (0, "", "", False)


def test_a_timed_out_run_ends_with_the_timeout_exit_code(
    tool_executor_fake: ToolExecutorFake, scenario: Scenario
) -> None:
    """The fake ends a run that timed out with exit code 124, as the real executor does."""
    tool_executor_fake.script(
        _TOOL, ToolAnswer(exit_code=CONST_SANDBOX_TIMEOUT_EXIT_CODE, timed_out=True)
    )

    result = tool_executor_fake.run(scenario.request())

    assert (result.exit_code, result.timed_out) == (CONST_SANDBOX_TIMEOUT_EXIT_CODE, True)


def test_a_result_that_timed_out_with_another_exit_code_is_refused(
    tool_executor_fake: ToolExecutorFake, scenario: Scenario
) -> None:
    """A timeout has one exit code, so no executor or fake can report a different one."""
    run = tool_executor_fake.run(scenario.request()).run

    with pytest.raises(ValueError, match="exit code 124"):
        ToolResult(run=run, exit_code=0, timed_out=True)


# The real executor: what it asks bubblewrap for.


def _sandbox_command(scenario: Scenario, request: ToolRequest) -> tuple[list[str], list[str]]:
    """The bubblewrap options and the command inside the sandbox that the real executor builds."""
    command = SandboxToolExecutor(HostSandbox(bwrap_binary=Path("/usr/bin/bwrap"))).command(request)
    split = command.index("--", command.index("--chdir"))
    return command[:split], command[split + 1 :]


def _binds(options: list[str]) -> list[list[str]]:
    """Every bind option of a bubblewrap command line, as `[flag, source, destination]`."""
    return [options[i : i + 3] for i, flag in enumerate(options) if flag in {"--ro-bind", "--bind"}]


def _setenv(options: list[str]) -> dict[str, str]:
    """Every variable a bubblewrap command line sets for the sandboxed command."""
    return {options[i + 1]: options[i + 2] for i, flag in enumerate(options) if flag == "--setenv"}


def test_the_sandbox_confines_the_tool_to_the_tree_and_the_files_it_needs(
    scenario: Scenario,
) -> None:
    """The tool has no network and no inherited environment. It gets a read-only tree, read-only
    rules, a read-only install directory and a temporary HOME. The tree is its working directory."""
    options, _ = _sandbox_command(scenario, scenario.request())

    binds = _binds(options)
    needed = (scenario.tree, scenario.tools_dir, scenario.config_file, scenario.ruleset_file)
    assert {
        "isolation": [arg for arg in options if arg in _SANDBOX_ARGS],
        "network": "--share-net" in options,
        "writable binds": [bind for bind in binds if bind[0] == "--bind"],
        "read-only binds": [["--ro-bind", str(path), str(path)] in binds for path in needed],
        "home": _setenv(options)["HOME"],
        "private tmp": options[options.index("--tmpfs") + 1],
        "working directory": options[options.index("--chdir") + 1],
    } == {
        "isolation": list(_SANDBOX_ARGS),
        "network": False,
        "writable binds": [],
        "read-only binds": [True, True, True, True],
        "home": _PRIVATE_TMP,
        "private tmp": _PRIVATE_TMP,
        "working directory": str(scenario.tree),
    }


@pytest.mark.parametrize(
    ("limits", "cpu_seconds", "address_space_bytes"),
    [
        pytest.param(ToolLimits(), 600, 2 * 1024**3, id="default limits"),
        pytest.param(
            ToolLimits(cpu_seconds=7, address_space_bytes=3 * 1024**3),
            7,
            3 * 1024**3,
            id="limits of the request",
        ),
    ],
)
def test_the_sandbox_starts_the_tool_under_a_cpu_and_an_address_space_limit(
    scenario: Scenario, limits: ToolLimits, cpu_seconds: int, address_space_bytes: int
) -> None:
    """The tool runs through prlimit, by its full path. It gets the CPU limit and the address space
    limit of the request, which are 600 seconds and 2 GiB by default. Go tools also get a memory
    limit for their collector. Other programs ignore it."""
    options, command = _sandbox_command(scenario, scenario.request(limits=limits))

    assert (command, _setenv(options)["GOMEMLIMIT"]) == (
        [
            str(shutil.which("prlimit")),
            f"--cpu={cpu_seconds}",
            f"--as={address_space_bytes}",
            "--",
            str(scenario.stand_in),
            "scan",
            str(scenario.target),
        ],
        "1GiB",
    )


def test_the_environment_of_a_request_reaches_the_tool_but_cannot_lift_the_collector_limit(
    scenario: Scenario,
) -> None:
    """A variable of the request is set in the sandbox. A request that sets `GOMEMLIMIT` does not
    change it, because the limit of the executor wins."""
    request = scenario.request().model_copy(update={"env": {"FOO": "bar", "GOMEMLIMIT": "1"}})

    options, _ = _sandbox_command(scenario, request)

    seen = _setenv(options)
    assert (seen["FOO"], seen["GOMEMLIMIT"]) == ("bar", "1GiB")


def test_the_sandbox_sets_no_limit_on_the_number_of_processes(scenario: Scenario) -> None:
    """RLIMIT_NPROC counts every process of the user, so a limit would starve the host."""
    options, command = _sandbox_command(scenario, scenario.request())

    assert [arg for arg in (*options, *command) if "nproc" in arg.lower()] == []


def test_a_limit_under_two_gibibytes_of_address_space_is_refused() -> None:
    """Go tools reserve more address space than they use, so the floor of the limit is 2 GiB."""
    with pytest.raises(ValueError, match="address_space_bytes"):
        ToolLimits(address_space_bytes=2 * 1024**3 - 1)


def test_a_host_without_bubblewrap_is_refused(scenario: Scenario, tmp_path: Path) -> None:
    """The executor fails closed: it never runs a tool outside the sandbox."""
    executor = SandboxToolExecutor(HostSandbox(bwrap_binary=tmp_path / "no-bwrap"))

    with pytest.raises(SandboxError, match="bubblewrap") as refused:
        executor.run(scenario.request())

    assert refused.value.error_code == CONST_ERROR_CODE_SANDBOX


def test_a_host_without_prlimit_is_refused(
    scenario: Scenario, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Without prlimit the limits cannot be set, so the tool does not run."""
    monkeypatch.setenv("PATH", str(scenario.tools_dir))

    with pytest.raises(SandboxError, match="prlimit"):
        SandboxToolExecutor(HostSandbox(bwrap_binary=Path("/usr/bin/bwrap"))).run(
            scenario.request()
        )


def test_a_tool_with_no_binary_is_refused(scenario: Scenario) -> None:
    """A run that names a tool the host does not have is refused, never recorded as unknown."""
    request = scenario.request().model_copy(update={"tool": "no-such-review-tool"})

    with pytest.raises(SandboxError, match="no-such-review-tool"):
        SandboxToolExecutor(HostSandbox(bwrap_binary=Path("/usr/bin/bwrap"))).run(request)


# The real executor: what the sandbox gives the running tool.


def _probe(scenario: Scenario) -> dict[str, str]:
    """What the sandbox gave the stand-in, as the stand-in's `probe` reports it."""
    request = scenario.request("probe", "{targets}", str(scenario.ruleset_file))
    stdout = SandboxToolExecutor().run(request).stdout
    report = re.findall(r"^(Max [a-z ]+?)\s{2,}(\S+)\s+(\S+)", stdout, re.MULTILINE)
    return {
        **{name: f"{soft} {hard}" for name, soft, hard in report},
        **dict(re.findall(r"^([A-Z]+)=(.*)$", stdout, re.MULTILINE)),
        **dict(re.findall(r"^(INPUT \S+)=(\S+)$", stdout, re.MULTILINE)),
    }


@pytest.mark.bwrap
def test_the_tool_sees_no_network_no_host_environment_and_only_read_only_inputs(
    scenario: Scenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The tool finds a loopback interface only and none of the variables of the host. It has a
    private HOME. It can read the tree and the ruleset, but it cannot write them."""
    monkeypatch.setenv("DEVOPS_TOOL_TEST_SECRET", "host-value")
    tree_file = f"INPUT {scenario.target / 'app.py'}"
    ruleset = f"INPUT {scenario.ruleset_file}"

    seen = _probe(scenario)

    assert {name: seen[name] for name in ("INTERFACES", "SECRET", "HOME", tree_file, ruleset)} == {
        "INTERFACES": "lo,",
        "SECRET": "",
        "HOME": _PRIVATE_TMP,
        tree_file: "read-only",
        ruleset: "read-only",
    }


@pytest.mark.bwrap
def test_the_tool_runs_under_the_limits_and_none_on_processes(scenario: Scenario) -> None:
    """The kernel reports the CPU limit and the address space limit on the tool. The collector
    limit is in its environment. Its process limit is the limit of the host."""
    soft, hard = resource.getrlimit(resource.RLIMIT_NPROC)

    def shown(limit: int) -> str:
        return "unlimited" if limit == resource.RLIM_INFINITY else str(limit)

    seen = _probe(scenario)

    assert {
        name: seen[name]
        for name in ("Max cpu time", "Max address space", "Max processes", "GOMEMLIMIT")
    } == {
        "Max cpu time": "600 600",
        "Max address space": f"{2 * 1024**3} {2 * 1024**3}",
        "Max processes": f"{shown(soft)} {shown(hard)}",
        "GOMEMLIMIT": "1GiB",
    }


def _running(marker: str) -> bool:
    """Whether any process of the host, in any namespace below it, has `marker` in its command."""
    for cmdline in Path("/proc").glob("[0-9]*/cmdline"):
        try:
            if marker.encode() in cmdline.read_bytes():
                return True
        except OSError:  # the process ended between the listing and the read
            continue
    return False


def test_the_process_scan_sees_a_running_process(tmp_path: Path, git: Callable[..., None]) -> None:
    """The control for the next test: the scan finds a process while it runs and not after."""
    repo = tmp_path / "scan-marker"
    repo.mkdir()
    git(repo, "init", "--quiet")
    process = subprocess.Popen(
        ["git", "-C", str(repo), "cat-file", "--batch"],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        seen_running = wait_until(lambda: _running(str(repo)))
    finally:
        process.kill()
        process.wait()

    assert (seen_running, wait_until(lambda: not _running(str(repo)))) == (True, True)


@pytest.mark.bwrap
def test_a_tool_that_runs_out_of_time_ends_with_its_whole_process_tree(
    scenario: Scenario,
) -> None:
    """The wall clock ends the sandbox, and the child the tool started goes with it. The run
    reports a timeout and the output the tool wrote before it."""
    request = scenario.request("hang", "{targets}", limits=ToolLimits(wall_seconds=2.0))

    result = SandboxToolExecutor().run(request)

    assert (
        result.timed_out,
        result.exit_code,
        result.stdout,
        wait_until(lambda: not _running(str(scenario.target))),
    ) == (True, CONST_SANDBOX_TIMEOUT_EXIT_CODE, "started\n", True)
