"""The network git calls of the implement job and the check of the git settings (GHSA).

`OriginGit` runs each call that reaches `origin` in a new git folder, with the token, and reads no
configuration file, hook or credential helper of the home folder or of the clone. Git runs for
real: through the real process runner where the environment of the child matters, and through
the process fake where the order of the calls matters. A loopback HTTP server that asks for Basic
credentials stands in for GitHub.
"""

from __future__ import annotations

import socket
import subprocess
import threading
from collections.abc import Callable, Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from devops_cli.core import process_hardening
from devops_cli.exceptions import GitOperationError
from devops_cli.exceptions.roadmap import GitSettingsError
from devops_cli.git.worktree_add import worktree_directory
from devops_cli.roadmap.implement import git_isolation
from devops_cli.roadmap.implement.git_isolation import OriginGit, refused_settings
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.implement_step import git_for_real
from tests.support.model_script import ModelScript, say, tool_calls
from tests.support.roadmap_implement import JobWorld, group_one_calls
from tests.support.roadmap_stage import StageRepo, run_git

pytestmark = pytest.mark.usefixtures("keyring_store")

BRANCH = "fix/1-the-job-drops-a-comment"
VALUE = "example-value-7"


def _recorder(path: Path, capture: Path, name: str) -> Path:
    """A program that reads its input and adds `<name> <GH_TOKEN or none>` to `capture`."""
    path.write_text(
        f"#!/bin/sh\ncat >/dev/null\nprintf '%s %s\\n' '{name}' \"${{GH_TOKEN:-none}}\" >> '{capture}'\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def _seen(capture: Path) -> str:
    return capture.read_text(encoding="utf-8") if capture.exists() else ""


@pytest.fixture
def work(stage_repo: StageRepo) -> str:
    """A commit of the clone that `origin` lacks, on no branch of `origin`."""
    run_git(stage_repo.clone, "commit", "-q", "--allow-empty", "-m", "work")
    return run_git(stage_repo.clone, "rev-parse", "HEAD")


@pytest.fixture
def capture(tmp_path: Path) -> Path:
    return tmp_path / "capture.txt"


@pytest.fixture
def planted(
    stage_repo: StageRepo, work: str, tmp_path: Path, capture: Path, monkeypatch: pytest.MonkeyPatch
) -> Callable[[str], None]:
    """Plant a hook folder with a `pre-push` hook and a credential helper in the home folder and in
    the configuration of the clone; `extra` adds lines to both files."""
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    _recorder(hooks / "pre-push", capture, "pre-push")
    helper = _recorder(tmp_path / "helper", capture, "helper")
    home = tmp_path / "job-home"
    home.mkdir()

    def plant(extra: str = "") -> None:
        lines = f"[core]\n\thooksPath = {hooks}\n[credential]\n\thelper = {helper}\n{extra}"
        (home / ".gitconfig").write_text(lines, encoding="utf-8")
        with (stage_repo.clone / ".git" / "config").open("a", encoding="utf-8") as config:
            config.write(lines)
        monkeypatch.setenv("HOME", str(home))

    return plant


class _Challenge(BaseHTTPRequestHandler):
    """Answers each request with 401 and a Basic challenge, and keeps its headers."""

    seen: list[dict[str, str]]

    def _refuse(self) -> None:
        self.seen.append(dict(self.headers.items()))
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="example"')
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        self._refuse()

    def do_POST(self) -> None:
        self._refuse()

    def log_message(self, *_args: object) -> None:
        return None


@pytest.fixture
def challenge() -> Iterator[tuple[str, list[dict[str, str]]]]:
    """The URL of a repository on a loopback server that asks for Basic credentials, and the
    headers of each request that it received."""
    seen: list[dict[str, str]] = []
    handler = type("Handler", (_Challenge,), {"seen": seen})
    server = HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/example/roadmap.git", seen
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture
def proxy() -> Iterator[socket.socket]:
    """A loopback socket that listens and that nothing should reach."""
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    listener.setblocking(False)
    try:
        yield listener
    finally:
        listener.close()


def _reached(listener: socket.socket) -> bool:
    try:
        connection, _ = listener.accept()
    except BlockingIOError:
        return False
    connection.close()
    return True


# ── The call with the token ───────────────────────────────────────────────────────────────


def test_a_push_runs_no_hook_and_no_helper_of_the_home_folder_or_of_the_clone(
    stage_repo: StageRepo, work: str, planted: Callable[[str], None], capture: Path
) -> None:
    planted("")

    OriginGit(stage_repo.clone, str(stage_repo.origin)).push(BRANCH, work)

    assert run_git(stage_repo.origin, "rev-parse", f"refs/heads/{BRANCH}") == work
    assert run_git(stage_repo.clone, "rev-parse", f"refs/remotes/origin/{BRANCH}") == work
    assert _seen(capture) == ""


def test_a_push_to_a_server_that_asks_for_credentials_asks_no_planted_helper_and_no_proxy(
    stage_repo: StageRepo,
    work: str,
    planted: Callable[[str], None],
    capture: Path,
    challenge: tuple[str, list[dict[str, str]]],
    proxy: socket.socket,
) -> None:
    """The helper and the proxy of the home folder and of the clone apply to no call: the server
    gets a request with no credential, and the push fails."""
    url, seen = challenge
    port = proxy.getsockname()[1]
    planted(f"[http]\n\tproxy = http://127.0.0.1:{port}\n\tsslVerify = false\n")

    with pytest.raises(GitOperationError, match="terminal prompts disabled"):
        OriginGit(stage_repo.clone, url).push(BRANCH, work)

    assert (_seen(capture), _reached(proxy), bool(seen)) == ("", False, True)
    assert [headers for headers in seen if "Authorization" in headers] == []


def test_a_fetch_writes_the_new_objects_and_the_ref_into_the_clone(stage_repo: StageRepo) -> None:
    other = stage_repo.origin.parent / "other"
    run_git(other.parent, "clone", "-q", str(stage_repo.origin), str(other))
    run_git(
        other,
        "-c",
        "user.name=b",
        "-c",
        "user.email=b@example.com",
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "moved",
    )
    run_git(other, "push", "-q", "origin", "main")
    moved = run_git(other, "rev-parse", "HEAD")

    OriginGit(stage_repo.clone, str(stage_repo.origin)).fetch("main")

    assert run_git(stage_repo.clone, "rev-parse", "refs/remotes/origin/main") == moved
    assert run_git(stage_repo.clone, "cat-file", "-t", moved) == "commit"


def test_a_lease_that_no_longer_holds_refuses_the_push(stage_repo: StageRepo, work: str) -> None:
    origin = OriginGit(stage_repo.clone, str(stage_repo.origin))
    origin.push(BRANCH, work)

    with pytest.raises(GitOperationError, match="`git push --quiet --no-verify --force-with-lease"):
        origin.push(BRANCH, None, lease="0" * 40)

    origin.push(BRANCH, None, lease=work)
    assert origin.heads(BRANCH) == ""


def _words(call: ProcessCall) -> str:
    """The subcommand of a git call, after its global options."""
    words = list(call.argv[1:])
    while words and words[0].startswith("-"):
        words = words[2:] if words[0] in ("-C", "-c") else words[1:]
    return words[0] if words else ""


@pytest.fixture
def recorded(
    process_fake: ProcessFake, config: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> list[str]:
    """The order of the sweeps, of the new folder and of the git calls, in a runner."""
    config(roadmap={"implement": {"in_runner": True}})
    order: list[str] = []

    def git(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        order.append(_words(call))
        return git_for_real(call)

    process_fake.answer("git", ProcessAnswer(side_effect=git))
    monkeypatch.setattr(
        process_hardening, "end_leftover_processes", lambda timeout=0.0: order.append("sweep")
    )
    made = git_isolation.tempfile.mkdtemp
    monkeypatch.setattr(
        git_isolation.tempfile, "mkdtemp", lambda **kw: (order.append("mkdtemp"), made(**kw))[1]
    )
    return order


def test_the_leftover_processes_end_before_the_check_before_the_folder_and_before_the_token_call(
    stage_repo: StageRepo, recorded: list[str], process_fake: ProcessFake
) -> None:
    OriginGit(stage_repo.clone, str(stage_repo.origin)).fetch("main")

    token_call = recorded.index("fetch")
    first, second, third = (i for i, word in enumerate(recorded) if word == "sweep")
    assert "config" in recorded[first:second]
    assert first == 0
    assert second < recorded.index("mkdtemp") < recorded.index("update-ref") < third
    assert third == token_call - 1
    fetch = next(call for call in process_fake.calls if _words(call) == "fetch")
    assert fetch.env is not None
    assert {key: fetch.env.get(key) for key in ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM")} == {
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
    }
    assert [word for word in fetch.argv if word.startswith(("credential.", "core.hooksPath"))] == [
        "credential.helper=",
        "credential.https://github.com.helper=",
        "credential.https://github.com.helper=!gh auth git-credential",
        "core.hooksPath=/dev/null",
    ]
    assert not Path(fetch.env["HOME"]).exists()


def test_a_refused_setting_ends_the_leftover_processes_before_the_check(
    stage_repo: StageRepo, recorded: list[str]
) -> None:
    """A refused setting stops the call before the folder exists. The leftover processes end first
    all the same, because the job writes to GitHub after the stop."""
    run_git(stage_repo.clone, "config", "credential.helper", VALUE)

    with pytest.raises(GitSettingsError) as refused:
        OriginGit(stage_repo.clone, str(stage_repo.origin)).fetch("main")

    assert (refused.value.settings, recorded[0], "mkdtemp" in recorded) == (
        ("credential.helper",),
        "sweep",
        False,
    )


def test_a_push_gives_the_token_only_to_the_call_in_the_new_folder(
    stage_repo: StageRepo, work: str, recorded: list[str], process_fake: ProcessFake
) -> None:
    OriginGit(stage_repo.clone, str(stage_repo.origin)).push(BRANCH, work)

    push = next(call for call in process_fake.calls if _words(call) == "push")
    assert ("--no-verify" in push.argv, push.argv[-1], push.cwd != stage_repo.clone) == (
        True,
        f"{work}:refs/heads/{BRANCH}",
        True,
    )
    assert recorded[recorded.index("push") - 1] == "sweep"


# ── The settings check ────────────────────────────────────────────────────────────────────


def test_the_settings_of_a_new_clone_pass_the_check(stage_repo: StageRepo) -> None:
    assert refused_settings(stage_repo.clone) == []


def test_an_alternates_file_of_the_clone_is_refused(stage_repo: StageRepo, tmp_path: Path) -> None:
    (stage_repo.clone / ".git" / "objects" / "info" / "alternates").write_text(
        f"{tmp_path}\n", encoding="utf-8"
    )

    assert refused_settings(stage_repo.clone) == ["objects/info/alternates"]


@pytest.mark.parametrize(
    ("settings", "attributes", "named"),
    [
        ({"filter.x.clean": VALUE}, "* filter=x\n", ["filter.x.clean", "filter ("]),
        ({"gpg.program": VALUE, "commit.gpgsign": "true"}, "", ["gpg.program"]),
        ({"credential.helper": VALUE}, "", ["credential.helper"]),
    ],
    ids=["filter", "gpg", "helper"],
)
def test_a_setting_that_a_turn_writes_stops_the_item_with_the_class_git_config(
    job_world: JobWorld, settings: dict[str, str], attributes: str, named: list[str]
) -> None:
    """The agent writes a setting in its turn. The item stops with the class `git_config` before
    the job runs `git add`, `git commit`, `git push` or `git fetch` again, and the comment names
    each key and holds no value."""
    planted_at: list[int] = []

    def plant() -> None:
        for key, value in settings.items():
            job_world.repo.git("config", key, value)
        if attributes:
            (worktree_directory(1, job_world.repo.clone) / ".gitattributes").write_text(
                attributes, encoding="utf-8"
            )
        planted_at.append(len(job_world.programs.calls))

    script = ModelScript(
        tool_calls(*group_one_calls()), say("Group 1 is done."), effects={2: plant}
    )

    applied = job_world.run(script)

    held = job_world.store.item(1)
    assert held is not None
    after = [_words(call) for call in job_world.programs.calls[planted_at[0] :]]
    comment = job_world.issue_comments()[-1]
    assert (applied.stopped, held.status, held.job_record.get("implement.failure")) == (
        (1,),
        "Blocked",
        "git_config",
    )
    assert {"add", "commit", "push", "fetch", "ls-remote"} & set(after) == set()
    assert ([name for name in named if name not in comment], VALUE in comment) == ([], False)


def test_the_check_runs_only_in_a_runner(stage_repo: StageRepo) -> None:
    """A person can keep a global filter, so outside a runner the check refuses nothing."""
    run_git(stage_repo.clone, "config", "credential.helper", VALUE)

    git_isolation.check_settings(stage_repo.clone)

    assert refused_settings(stage_repo.clone) == ["credential.helper"]


def test_a_setting_that_an_exit_check_writes_stops_the_push_of_the_stop_with_the_class_git_config(
    job_world: JobWorld, config: Callable[..., Path]
) -> None:
    """An exit check of the step runs code of the checkout after the check of the turn. It writes a
    setting and fails, and no repair round is left. The push of the stop meets the setting: the
    item stops with the class `git_config`, and the comment names the key and holds no value."""
    config(roadmap={"implement": {"in_runner": True, "repair_rounds": 0}})

    def lint(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        job_world.repo.git("config", "credential.helper", VALUE)
        return subprocess.CompletedProcess(list(call.argv), 1, "E999 example\n", "")

    job_world.programs.answer(
        lambda call: "ruff" in call.argv and "check" in call.argv,
        ProcessAnswer(side_effect=lint),
    )
    script = ModelScript(tool_calls(*group_one_calls()), say("Group 1 is done."))

    applied = job_world.run(script)

    held = job_world.store.item(1)
    assert held is not None
    comment = job_world.issue_comments()[-1]
    assert (applied.stopped, held.job_record.get("implement.failure")) == ((1,), "git_config")
    assert ("credential.helper" in comment, VALUE in comment) == (True, False)


def test_a_fetch_in_a_shallow_clone_gets_the_new_commit(
    stage_repo: StageRepo, tmp_path: Path
) -> None:
    """A run with `--source` can point to a shallow clone. The new git folder gets the `shallow`
    file of the clone, so git does not walk into parents that the clone does not hold."""
    url = f"file://{stage_repo.origin}"
    for name in ("one", "two"):
        run_git(stage_repo.clone, "commit", "-q", "--allow-empty", "-m", name)
    run_git(stage_repo.clone, "push", "-q", "origin", "HEAD:main")
    shallow = tmp_path / "shallow"
    run_git(tmp_path, "clone", "-q", "--depth", "1", url, str(shallow))
    run_git(stage_repo.clone, "commit", "-q", "--allow-empty", "-m", "three")
    run_git(stage_repo.clone, "push", "-q", "origin", "HEAD:main")
    moved = run_git(stage_repo.clone, "rev-parse", "HEAD")

    OriginGit(shallow, url).fetch("main")

    assert (
        run_git(shallow, "rev-parse", "refs/remotes/origin/main"),
        run_git(shallow, "rev-parse", "--is-shallow-repository"),
    ) == (moved, "true")


def test_a_changed_shallow_file_goes_back_into_the_clone_and_replaces_a_link(
    tmp_path: Path,
) -> None:
    common, made = tmp_path / "common", tmp_path / "repo.git"
    common.mkdir()
    made.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.write_text("kept\n", encoding="utf-8")
    (common / "shallow").symlink_to(elsewhere)
    (made / "shallow").write_text("a" * 40 + "\n", encoding="utf-8")

    git_isolation._Folder(made, tmp_path / "home", common).keep_shallow()

    held = common / "shallow"
    assert (held.is_symlink(), held.read_text(encoding="utf-8"), elsewhere.read_text()) == (
        False,
        "a" * 40 + "\n",
        "kept\n",
    )
