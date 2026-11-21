"""The network git calls of the implement job (GHSA).

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
from devops_cli.roadmap.implement import git_isolation
from devops_cli.roadmap.implement.git_isolation import OriginGit
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.implement_step import git_for_real
from tests.support.model_script import ModelScript, say, tool_calls
from tests.support.roadmap_implement import JobWorld, group_one_calls, link_shallow
from tests.support.roadmap_stage import StageRepo, run_git

pytestmark = pytest.mark.usefixtures("keyring_store")

BRANCH = "fix/1-the-job-drops-a-comment"


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


@pytest.mark.parametrize(
    "lines",
    [
        '[url "{url}"]\n\tinsteadOf = {origin}\n',
        '[url "{url}"]\n\tpushInsteadOf = {origin}\n',
    ],
    ids=["insteadOf", "pushInsteadOf"],
)
def test_a_push_sends_nothing_to_a_url_that_the_home_folder_or_the_clone_names(
    stage_repo: StageRepo,
    work: str,
    planted: Callable[[str], None],
    capture: Path,
    challenge: tuple[str, list[dict[str, str]]],
    lines: str,
) -> None:
    """An `insteadOf` or a `pushInsteadOf` in the home folder and in the clone names a server that
    asks for credentials. The push goes to `origin`, and the server gets no request, so it gets no
    token."""
    url, seen = challenge
    planted(lines.format(url=url, origin=stage_repo.origin))

    OriginGit(stage_repo.clone, str(stage_repo.origin)).push(BRANCH, work)

    assert run_git(stage_repo.origin, "rev-parse", f"refs/heads/{BRANCH}") == work
    assert (seen, _seen(capture)) == ([], "")


def test_a_push_runs_no_hook_of_the_hooks_folder_of_the_clone(
    stage_repo: StageRepo, work: str, capture: Path
) -> None:
    """git looks for a hook in the hooks folder of the clone when no `core.hooksPath` is set. A
    `pre-push` hook there does not run, and the branch is on `origin`."""
    hooks = Path(
        run_git(stage_repo.clone, "rev-parse", "--path-format=absolute", "--git-path", "hooks")
    )
    hooks.mkdir(parents=True, exist_ok=True)
    _recorder(hooks / "pre-push", capture, "pre-push")

    OriginGit(stage_repo.clone, str(stage_repo.origin)).push(BRANCH, work)

    assert (run_git(stage_repo.origin, "rev-parse", f"refs/heads/{BRANCH}"), _seen(capture)) == (
        work,
        "",
    )


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


def test_the_leftover_processes_end_before_the_folder_and_before_the_token_call(
    stage_repo: StageRepo, recorded: list[str], process_fake: ProcessFake
) -> None:
    OriginGit(stage_repo.clone, str(stage_repo.origin)).fetch("main")

    token_call = recorded.index("fetch")
    first, second = (i for i, word in enumerate(recorded) if word == "sweep")
    assert first == 0
    assert first < recorded.index("mkdtemp") < recorded.index("update-ref") < second
    assert second == token_call - 1
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


def test_a_link_at_the_shallow_file_ends_the_leftover_processes_before_the_refusal(
    stage_repo: StageRepo, recorded: list[str]
) -> None:
    """A link at the `shallow` file stops the call before the call with the token. The leftover
    processes end first all the same, because the job writes to GitHub after the stop."""
    link_shallow(stage_repo)

    with pytest.raises(GitSettingsError) as refused:
        OriginGit(stage_repo.clone, str(stage_repo.origin)).fetch("main")

    assert (refused.value.settings, recorded[0], "fetch" in recorded) == (
        ("shallow",),
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


# ── The shallow file ──────────────────────────────────────────────────────────────────────


def test_a_link_that_an_exit_check_writes_at_the_shallow_file_stops_the_push_of_the_stop(
    job_world: JobWorld, config: Callable[..., Path]
) -> None:
    """An exit check of the step runs code of the checkout. It makes the `shallow` file of the
    clone a link and fails, and no repair round is left. The push of the stop meets the link: the
    item stops with the class `git_config`, and the comment names `shallow`."""
    config(roadmap={"implement": {"in_runner": True, "repair_rounds": 0}})

    def lint(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        link_shallow(job_world.repo)
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
    assert "`shallow`" in comment


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


def test_a_link_at_the_shallow_file_of_the_clone_stops_the_fetch(
    stage_repo: StageRepo, tmp_path: Path
) -> None:
    """git never makes `shallow` a link. The copy into the new git folder does not follow a link
    there: the fetch stops with `GitSettingsError`, which gives the class `git_config`."""
    url = f"file://{stage_repo.origin}"
    victim = tmp_path / "victim"
    victim.write_text(run_git(stage_repo.clone, "rev-parse", "HEAD") + "\n", encoding="utf-8")
    common = run_git(stage_repo.clone, "rev-parse", "--path-format=absolute", "--git-common-dir")
    (Path(common) / "shallow").symlink_to(victim)

    with pytest.raises(GitSettingsError) as refused:
        OriginGit(stage_repo.clone, url).fetch("main")

    assert refused.value.settings == ("shallow",)


def test_the_write_back_of_the_shallow_file_follows_no_link_at_a_temporary_name(
    tmp_path: Path,
) -> None:
    """The new text goes into a new file with a random name, so a link that waits at a fixed
    temporary name, such as `shallow.devops-cli`, is not followed, and no temporary file stays."""
    common, made = tmp_path / "common", tmp_path / "repo.git"
    common.mkdir()
    made.mkdir()
    victim = tmp_path / "victim"
    victim.write_text("kept\n", encoding="utf-8")
    (common / "shallow.devops-cli").symlink_to(victim)
    (made / "shallow").write_text("a" * 40 + "\n", encoding="utf-8")

    git_isolation._Folder(made, tmp_path / "home", common).keep_shallow()

    held = common / "shallow"
    assert (
        victim.read_text(encoding="utf-8"),
        held.is_symlink(),
        held.read_text(encoding="utf-8"),
        sorted(entry.name for entry in common.iterdir()),
    ) == ("kept\n", False, "a" * 40 + "\n", ["shallow", "shallow.devops-cli"])


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
