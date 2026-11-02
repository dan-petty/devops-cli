"""The contract of the review-tool executor: the real sandbox executor and the fake answer a
request the same way (#772, ADR 0007).

A review tool starts through a `ToolExecutor`. The real executor builds a bubblewrap command and
starts it through `run_subprocess`. `ToolExecutorFake` starts nothing. Each shared case runs over
both, with a stand-in for the tool on disk. The stand-in is a shell script named after a tool that
`tools.lock` pins, and a test puts it first on PATH. The real side carries the `bwrap` mark, so
tests skip it where bubblewrap is missing.

`DirectToolExecutor` starts the tool itself, as a review did before the sandbox. The floor of the
suite allows git and no other program, so its cases start git as the tool, in a temporary
repository. They check what the sandbox cases check of the start: the directory, the standard
input, the arguments and the environment. The cases of a record that the direct executor cannot
complete, and of the network of a direct run, also run over the fake with `require_commit=False`,
`require_files=False` and `network=CONST_TOOL_NETWORK_HOST`. That fake stands in for the direct
executor and must record as it does.

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
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from devops_cli.ai.run_store import digest, file_digest
from devops_cli.config.constants import (
    CONST_SANDBOX_TIMEOUT_EXIT_CODE,
    CONST_TOOL_DIGEST_UNAVAILABLE,
    CONST_TOOL_EXECUTOR_DIRECT,
    CONST_TOOL_NETWORK_HOST,
)
from devops_cli.config.defaults import DEFAULT_REPOMAP_MAX_FILE_SIZE_BYTES
from devops_cli.exceptions.sandbox import (
    SandboxError,
    SandboxUnavailableError,
    SandboxValidationError,
)
from devops_cli.sandbox.host import DEFAULT_HOST_SANDBOX_POLICY, HostSandbox
from devops_cli.security.tool_executor import (
    DirectToolExecutor,
    KubeApiNetwork,
    SandboxToolExecutor,
    ToolExecutor,
    ToolLimits,
    ToolRequest,
    ToolResult,
    ToolRun,
)
from devops_cli.tools_lock import load_tools_lock
from tests.support.fakes.process import ProcessAnswer, ProcessCall
from tests.support.fakes.tool_executor import FAKE_EXECUTOR, ToolAnswer, ToolExecutorFake
from tests.support.waits import wait_until

if TYPE_CHECKING:
    from tests.support.fakes.git import GitFake

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
where)
  echo "CWD=$(pwd)"
  ;;
stdin)
  echo "STDIN=[$(cat)]"
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

    @property
    def interpreter(self) -> Path:
        """A copy of the stand-in that the host PATH does not name, as the interpreter of the
        `.venv` of a reviewed repository is no program of the PATH."""
        return self.tools_dir / "interpreter"

    def request(
        self, *arguments: str, limits: ToolLimits | None = None, program: Path | None = None
    ) -> ToolRequest:
        """A request to run the stand-in over the tree's `src`, with the scenario's files. With a
        `program`, the request starts that program in place of the tool on PATH."""
        return ToolRequest(
            tool=_TOOL,
            arguments=arguments or ("scan", "{targets}"),
            workdir=self.tree,
            targets=(self.target,),
            config_files=(self.config_file,),
            ruleset_files=(self.ruleset_file,),
            read_only_binds=(self.tools_dir,),
            limits=limits or ToolLimits(),
            **({} if program is None else {"program": program}),
        )


def _git_toplevel(call: ProcessCall) -> str:
    argv = call.argv
    if "-C" in argv:
        target_arg = argv[argv.index("-C") + 1]
        target_path = Path(target_arg).resolve()
        toplevel = target_path if target_path.is_dir() else target_path.parent
        if toplevel.name == "src":
            toplevel = toplevel.parent
        return f"{toplevel}\n"
    cwd = call.cwd or Path.cwd()
    return f"{Path(cwd).resolve()}\n"


def _handle_git_rev_parse(call: ProcessCall) -> ProcessAnswer:
    argv = call.argv
    if "--show-toplevel" in argv:
        return ProcessAnswer(stdout=_git_toplevel(call))
    if "broken" in str(call.cwd) or any("broken" in arg for arg in argv):
        return ProcessAnswer(returncode=128, stderr="fatal: not a git repository\n")
    if any("no-such-branch" in arg for arg in argv):
        return ProcessAnswer(returncode=128, stderr="fatal: Needed a single revision\n")
    if "fresh" in str(call.cwd) or any("fresh" in arg for arg in argv):
        return ProcessAnswer(returncode=1, stderr="fatal: Needed a single revision\n")
    return ProcessAnswer(stdout="1" * 40 + "\n")


def _target_dirty_lines(root: Path, target_name: str) -> list[str]:
    target_path = root / target_name
    lines: list[str] = []
    if target_path.is_file():
        if (
            target_name == "src/app.py"
            and target_path.read_text(encoding="utf-8") != "print('hello')\n"
        ):
            lines.append(f" M {target_name}\n")
    elif target_path.is_dir():
        app = target_path / "app.py"
        if app.exists() and app.read_text(encoding="utf-8") != "print('hello')\n":
            lines.append(f" M {target_name}/app.py\n")
        for p in target_path.iterdir():
            if p.name != "app.py":
                lines.append(f"?? {target_name}/{p.name}\n")
    return lines


def _handle_git_status(call: ProcessCall) -> ProcessAnswer:
    argv = call.argv
    if "-C" in argv:
        root = Path(argv[argv.index("-C") + 1]).resolve()
    else:
        root = Path(call.cwd or Path.cwd()).resolve()

    target_names = argv[argv.index("--") + 1 :] if "--" in argv else []
    dirty_lines: list[str] = []
    for name in target_names:
        dirty_lines.extend(_target_dirty_lines(root, name))
    return ProcessAnswer(stdout="".join(dirty_lines))


def _handle_tool_executor_git(call: ProcessCall) -> ProcessAnswer:
    argv = call.argv
    if "--version" in argv:
        return ProcessAnswer(stdout="git version 2.43.0\n")
    if "rev-parse" in argv:
        return _handle_git_rev_parse(call)
    if "hash-object" in argv:
        return ProcessAnswer(stdout="e69de29bb2d1d6434b8b29ae775ad8c2e48c5391\n")
    if "var" in argv and "GIT_AUTHOR_IDENT" in argv:
        env = call.env or {}
        name = env.get("GIT_AUTHOR_NAME", "Review Tool")
        email = env.get("GIT_AUTHOR_EMAIL", "tool@example.com")
        return ProcessAnswer(stdout=f"{name} <{email}> 1234567890 +0000\n")
    if "status" in argv:
        return _handle_git_status(call)
    return ProcessAnswer()


def _handle_tool_executor_other(call: ProcessCall) -> ProcessAnswer:
    res = subprocess.run(
        call.argv,
        input=call.stdin if isinstance(call.stdin, str) else None,
        cwd=call.cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=call.timeout,
    )
    return ProcessAnswer(returncode=res.returncode, stdout=res.stdout, stderr=res.stderr)


@pytest.fixture(autouse=True)
def _answer_tool_executor_git(git_fake: GitFake) -> None:
    git_fake.answer(
        lambda call: bool(call.argv and Path(call.argv[0]).name == "git"),
        _handle_tool_executor_git,
    )
    git_fake.answer(
        lambda call: bool(call.argv and Path(call.argv[0]).name != "git"),
        _handle_tool_executor_other,
    )


@pytest.fixture
def scenario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Scenario:
    """A one-commit git tree with a stand-in for the tool first on PATH."""
    tree = tmp_path / "tree"
    (tree / "src").mkdir(parents=True)
    (tree / "src" / "app.py").write_text("print('hello')\n", encoding="utf-8")
    (tree / ".git").mkdir(parents=True, exist_ok=True)
    (tree / ".git" / "index").write_bytes(b"dummy_index_bytes\n")
    commit = "1" * 40

    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    stand_in = tools_dir / _TOOL
    stand_in.write_text(_STAND_IN, encoding="utf-8")
    stand_in.chmod(0o755)
    shutil.copy2(stand_in, tools_dir / "interpreter")
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


@pytest.mark.parametrize("success", [True, False])
def test_the_settled_record_of_a_run_holds_its_exit_code_and_the_success_its_caller_decided(
    executor: ToolExecutor, scenario: Scenario, success: bool
) -> None:
    """The executor builds the record before the tool starts, so the record of its answer says
    nothing of how the run ended. An executor that keeps no records changes nothing on a settle."""
    result = executor.run(scenario.request())

    executor.settle(result, success=success)

    assert (result.run.exit_code, result.run.success, result.settled(success=success)) == (
        None,
        None,
        result.run.model_copy(update={"exit_code": 3, "success": success}),
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


def test_a_request_that_names_a_program_starts_it_and_records_it_by_its_name(
    executor: ToolExecutor, scenario: Scenario
) -> None:
    """Mypy runs from the interpreter of the `.venv` of the reviewed repository, which the PATH of
    the host does not name. A request names that program. The record names the tool, and the
    program by its file name, not by its path, so the same scan records the same template. With
    no distribution of the tool beside the program, the version is the pin of `tools.lock` and the
    digest is the digest of the program file."""
    result = executor.run(scenario.request(program=scenario.interpreter))

    assert (
        result.stdout,
        result.run.tool,
        result.run.version,
        result.run.binary_sha256,
        result.run.argv_template,
    ) == (
        f"scanned: {scenario.target}\n",
        _TOOL,
        scenario.locked_version,
        scenario.binary_sha256,
        ("interpreter", "scan", "{targets}"),
    )


def test_a_request_names_its_program_by_an_absolute_path(scenario: Scenario) -> None:
    """A relative program would start another program in each directory that a run starts in."""
    with pytest.raises(ValidationError, match="program"):
        scenario.request(program=Path("interpreter"))


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
        "SANDBOX_VALIDATION_ERROR",
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


def test_a_ruleset_file_below_a_bind_is_digested_at_any_size(
    executor: ToolExecutor, scenario: Scenario, tmp_path: Path
) -> None:
    """A database file in a data directory of the tool is data that devops-cli or the user put
    there. The record reads it as a stream, so a file over the cap still gets a digest (#2130)."""
    database = tmp_path / "database"
    database.mkdir()
    oversized = _file_over_the_size_cap(database)
    request = scenario.request().model_copy(
        update={
            "ruleset_files": (oversized,),
            "read_only_binds": (scenario.tools_dir, database),
        }
    )

    run = executor.run(request).run

    assert run.ruleset_digest == digest([file_digest(oversized)])


def test_a_config_file_below_a_bind_is_refused_when_it_is_too_large(
    executor: ToolExecutor, scenario: Scenario, tmp_path: Path
) -> None:
    """Only a ruleset file below a bind has no cap. A config file over the cap stops the run, also
    below a bind (#2130)."""
    database = tmp_path / "database"
    database.mkdir()
    request = scenario.request().model_copy(
        update={
            "config_files": (_file_over_the_size_cap(database),),
            "read_only_binds": (scenario.tools_dir, database),
        }
    )

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
    executor: ToolExecutor, scenario: Scenario, tmp_path: Path
) -> None:
    """A fresh checkout holds no commit yet, so the record holds none."""
    fresh = tmp_path / "fresh"
    (fresh / "src").mkdir(parents=True)
    (fresh / ".git").mkdir(parents=True, exist_ok=True)
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

    assert refused.value.error_code == "SANDBOX_ERROR"


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


# The real executor: where the sandbox starts the tool and what it reads there.


@pytest.fixture
def caller_input() -> Iterator[None]:
    """The standard input of the test process holds `caller input` until the test ends."""
    read_end, write_end = os.pipe()
    os.write(write_end, b"caller input")
    os.close(write_end)
    saved = os.dup(0)
    os.dup2(read_end, 0)
    os.close(read_end)
    try:
        yield
    finally:
        os.dup2(saved, 0)
        os.close(saved)


@pytest.mark.bwrap
def test_the_sandbox_starts_the_tool_in_the_tree_or_in_the_directory_the_request_names(
    scenario: Scenario, tmp_path: Path
) -> None:
    """A scan that must not read the files of the tree starts in a scratch directory of its own,
    outside the tree. A request with no such directory starts the tool in the tree."""
    scratch = (tmp_path / "scratch").resolve()
    scratch.mkdir()
    sandbox = SandboxToolExecutor()

    in_scratch = sandbox.run(scenario.request("where").model_copy(update={"cwd": scratch}))
    in_tree = sandbox.run(scenario.request("where"))

    assert (in_scratch.stdout, in_tree.stdout) == (
        f"CWD={scratch}\n",
        f"CWD={scenario.tree.resolve()}\n",
    )


@pytest.mark.bwrap
@pytest.mark.usefixtures("caller_input")
def test_the_sandbox_gives_the_tool_an_empty_standard_input(scenario: Scenario) -> None:
    """Under `devops mcp` the standard input of the caller is the request stream of the client.
    A tool that read it would take the stream (#1079)."""
    assert SandboxToolExecutor().run(scenario.request("stdin")).stdout == "STDIN=[]\n"


@pytest.mark.bwrap
def test_the_sandbox_names_itself_in_the_record_of_its_run(scenario: Scenario) -> None:
    """The record of a run in the sandbox says so, as the record of a direct run says it was not."""
    assert SandboxToolExecutor().run(scenario.request("where")).run.executor == "sandbox"


# The direct executor: git is the one program that the floor of the suite lets a test start.


@pytest.fixture(params=["direct", "fake"])
def direct_executor(request: pytest.FixtureRequest) -> ToolExecutor:
    """The direct executor, then the fake that stands in for it and records as it does."""
    if request.param == "direct":
        return DirectToolExecutor()
    return ToolExecutorFake(
        require_commit=False, require_files=False, network=CONST_TOOL_NETWORK_HOST
    )


def _git_request(scenario: Scenario, *arguments: str, **fields: object) -> ToolRequest:
    """A request to run git over the tree of the scenario, as a review tool."""
    return scenario.request().model_copy(update={"tool": "git", "arguments": arguments, **fields})


def test_the_direct_executor_starts_the_tool_with_the_arguments_in_the_directory_of_the_request(
    scenario: Scenario, tmp_path: Path
) -> None:
    """The tool gets the request's arguments, `{targets}` replaced by the paths of the targets. It
    starts in the directory the request names, and in the tree when there is none."""
    elsewhere = (tmp_path / "elsewhere").resolve()
    elsewhere.mkdir()
    (elsewhere / ".git").mkdir(parents=True, exist_ok=True)
    show_toplevel = ("rev-parse", "--show-toplevel")
    direct = DirectToolExecutor()

    in_elsewhere = direct.run(_git_request(scenario, *show_toplevel, cwd=elsewhere))
    in_tree = direct.run(_git_request(scenario, *show_toplevel))
    of_target = direct.run(_git_request(scenario, "-C", "{targets}", *show_toplevel))

    assert (in_elsewhere.stdout, in_tree.stdout, of_target.stdout) == (
        f"{elsewhere}\n",
        f"{scenario.tree.resolve()}\n",
        f"{scenario.tree.resolve()}\n",
    )


def test_the_direct_executor_starts_the_program_of_a_request_in_place_of_the_tool_on_path(
    scenario: Scenario,
) -> None:
    """The stand-in of the tool is first on PATH, and it prints nothing for `rev-parse`. A request
    that names git as its program starts git, and the record names git as the program."""
    git = Path(str(shutil.which("git")))

    result = DirectToolExecutor().run(scenario.request("rev-parse", "--show-toplevel", program=git))

    assert (result.stdout, result.run.tool, result.run.argv_template) == (
        f"{scenario.tree.resolve()}\n",
        _TOOL,
        ("git", "rev-parse", "--show-toplevel"),
    )


def test_the_direct_executor_gives_the_tool_the_environment_of_the_request(
    scenario: Scenario,
) -> None:
    """The request's variables reach the tool."""
    identity = {"GIT_AUTHOR_NAME": "Review Tool", "GIT_AUTHOR_EMAIL": "tool@example.com"}

    result = DirectToolExecutor().run(
        _git_request(scenario, "var", "GIT_AUTHOR_IDENT", env=identity)
    )

    assert result.stdout.startswith("Review Tool <tool@example.com> ")


@pytest.mark.usefixtures("caller_input")
def test_the_direct_executor_gives_the_tool_an_empty_standard_input(scenario: Scenario) -> None:
    """The hash of the empty blob is the hash of an empty standard input (#1079)."""
    empty_blob = "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391\n"

    result = DirectToolExecutor().run(_git_request(scenario, "hash-object", "--stdin"))

    assert result.stdout == empty_blob


def test_the_direct_executor_answers_a_failure_of_the_tool_and_records_the_run(
    scenario: Scenario,
) -> None:
    """A tool that fails ends in its exit code and its output, not in an error of the executor. The
    record names the tool, the commit of the tree and the arguments."""
    request = _git_request(scenario, "rev-parse", "--verify", "refs/heads/no-such-branch")

    result = DirectToolExecutor().run(request)

    assert (result.exit_code, result.timed_out, result.run.commit, result.run.argv_template) == (
        128,
        False,
        scenario.commit,
        ("git", "rev-parse", "--verify", "refs/heads/no-such-branch"),
    )


def test_the_direct_executor_records_no_commit_for_a_checkout_that_git_cannot_read(
    direct_executor: ToolExecutor, scenario: Scenario, tmp_path: Path
) -> None:
    """A scan must end as it ended before the executor existed. The sandbox executor refuses a
    checkout that git does not trust. The direct executor starts the tool and records no commit,
    and so does the fake that stands in for it."""
    broken = tmp_path / "broken"
    (broken / "src").mkdir(parents=True)
    (broken / ".git").mkdir()
    request = _git_request(scenario, "--version", workdir=broken, targets=(broken / "src",))

    result = direct_executor.run(request)

    assert (result.exit_code, result.run.commit) == (0, None)


@pytest.mark.parametrize("unreadable", ["config_files", "ruleset_files"])
def test_the_direct_executor_records_a_file_it_cannot_digest_and_still_starts_the_tool(
    unreadable: str, direct_executor: ToolExecutor, scenario: Scenario
) -> None:
    """A scan must end as it ended before the record existed. A config file or a ruleset file that
    the record cannot read as a regular file is recorded as unavailable, and the tool starts all
    the same. The fake that stands in for the direct executor records it in the same way. The
    sandbox executor refuses such a file: it must bind the file into the sandbox."""
    config = digest([file_digest(scenario.config_file)])
    ruleset = digest([file_digest(scenario.ruleset_file)])
    request = _git_request(scenario, "--version", **{unreadable: (scenario.target,)})

    result = direct_executor.run(request)

    assert (result.exit_code, result.run.config_digest, result.run.ruleset_digest) == (
        0,
        CONST_TOOL_DIGEST_UNAVAILABLE if unreadable == "config_files" else config,
        CONST_TOOL_DIGEST_UNAVAILABLE if unreadable == "ruleset_files" else ruleset,
    )


def test_the_direct_executor_records_the_network_of_the_host(
    direct_executor: ToolExecutor, scenario: Scenario
) -> None:
    """A tool that the direct executor starts has the whole network of the host, and the record
    says so. The fake that stands in for the direct executor records it in the same way."""
    result = direct_executor.run(_git_request(scenario, "--version"))

    assert (result.exit_code, result.run.network) == (0, CONST_TOOL_NETWORK_HOST)


def test_the_direct_executor_refuses_a_network_profile_before_it_starts_the_tool(
    direct_executor: ToolExecutor, scenario: Scenario
) -> None:
    """The direct executor gives a tool the whole network of the host, so it cannot give the tool
    a network profile. It refuses the request before the tool starts, and so does the fake that
    stands in for it. The floor of the suite refuses to start Popeye, so a start raises another
    error."""
    request = ToolRequest(
        tool="popeye",
        arguments=("version",),
        workdir=scenario.tree,
        targets=(scenario.target,),
        network=KubeApiNetwork(),
    )

    with pytest.raises(SandboxError, match="cannot run the network profile kube-api"):
        direct_executor.run(request)


def test_each_executor_names_itself_in_the_record_of_its_run(scenario: Scenario) -> None:
    """A reader of a record sees whether the run was confined: the direct executor started the tool
    as a child process of devops-cli."""
    direct = DirectToolExecutor().run(_git_request(scenario, "--version"))
    fake = ToolExecutorFake().run(scenario.request())

    assert (direct.run.executor, fake.run.executor) == (CONST_TOOL_EXECUTOR_DIRECT, FAKE_EXECUTOR)


def test_a_record_that_names_no_executor_is_no_record(scenario: Scenario) -> None:
    """A reader of a record must see whether the run was confined, so the name is never empty."""
    run = ToolExecutorFake().run(scenario.request()).run

    with pytest.raises(ValidationError) as raised:
        ToolRun.model_validate({**run.model_dump(), "executor": ""})
    assert len(raised.value.errors()) > 0


def test_the_direct_executor_refuses_a_target_outside_the_tree_before_it_starts_the_tool(
    scenario: Scenario, tmp_path: Path
) -> None:
    """The refusal of the sandbox executor holds for the direct one."""
    outside = tmp_path / "outside"
    outside.mkdir()

    with pytest.raises(SandboxValidationError, match="outside the tree"):
        DirectToolExecutor().run(_git_request(scenario, "status", targets=(outside,)))


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


def test_the_sandbox_starts_the_program_of_a_request_by_its_path_under_the_limits(
    scenario: Scenario,
) -> None:
    """The sandbox starts the program that the request names, not the tool on PATH, and not the
    file that a link of the program leads to: the `python` of a `.venv` is a link to the
    interpreter it was made from, and only the path of the link finds the `.venv`. The directory
    of the program is one of the read-only binds of the request."""
    options, command = _sandbox_command(scenario, scenario.request(program=scenario.interpreter))

    assert (
        command,
        ["--ro-bind", str(scenario.tools_dir), str(scenario.tools_dir)] in _binds(options),
    ) == (
        [
            str(shutil.which("prlimit")),
            "--cpu=600",
            f"--as={2 * 1024**3}",
            "--",
            str(scenario.interpreter),
            "scan",
            str(scenario.target),
        ],
        True,
    )


def test_a_program_that_is_no_file_is_refused(scenario: Scenario, tmp_path: Path) -> None:
    """A run of a program that the host does not have is refused before anything starts."""
    request = scenario.request(program=tmp_path / "no-such-interpreter")

    with pytest.raises(SandboxError, match="no-such-interpreter"):
        SandboxToolExecutor(HostSandbox(bwrap_binary=Path("/usr/bin/bwrap"))).run(request)


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
    """The executor fails closed: it never runs a tool outside the sandbox. The refusal says that
    the host cannot start the sandbox, so a scan reports a coverage gap (#2096)."""
    executor = SandboxToolExecutor(HostSandbox(bwrap_binary=tmp_path / "no-bwrap"))

    with pytest.raises(SandboxUnavailableError, match="bubblewrap") as refused:
        executor.run(scenario.request())

    assert refused.value.error_code == "SANDBOX_UNAVAILABLE_ERROR"


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


@pytest.mark.bwrap
def test_the_process_scan_sees_a_running_process(tmp_path: Path) -> None:
    """The control for the next test: the scan finds a process while it runs and not after."""
    repo = tmp_path / "scan-marker"
    repo.mkdir()
    (repo / ".git").mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(
        [
            "bwrap",
            "--die-with-parent",
            "--ro-bind",
            "/",
            "/",
            "--bind",
            str(repo),
            str(repo),
            "sleep",
            "30",
        ],
        stdin=subprocess.DEVNULL,
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
