"""`devops install-tools`: every tool from the tools lock, at its exact version (#1142)."""

from __future__ import annotations

import gzip
import hashlib
import io
import os
import subprocess
import tarfile
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from typer.testing import CliRunner

from devops_cli.commands import install_tools
from devops_cli.commands.install_tools import (
    _PLATFORM,
    _download,
    _verify_sha256,
    install_binary,
    install_managed_tools,
    install_python_tool,
)
from devops_cli.commands.install_tools import app as install_tools_app
from devops_cli.exceptions import (
    ChecksumMismatchError,
    SSRFBlockedError,
    ToolDownloadError,
    ToolExecutionError,
)
from devops_cli.tools_lock import (
    LOCK_DIR,
    Artifact,
    BinaryTool,
    PythonTool,
    ToolsLock,
    installed_commands,
    load_tools_lock,
)
from tests.web_fakes import StubWeb

runner = CliRunner()

ASSET_URL = "https://example.com/releases/mytool"
EXECUTABLE = b"#!/bin/sh\necho mytool\n"


def _tar_gz(members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, data in members.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def _binary_entry(
    artifact: bytes,
    *,
    name: str = "mytool",
    archive_format: str = "binary",
    member: str | None = None,
) -> BinaryTool:
    """A lock entry for `name` 1.2.3 whose build for this platform is `artifact`, served at
    `https://example.com/releases/<name>`."""
    return BinaryTool.model_validate(
        {
            "version": "1.2.3",
            "description": "A tool under test",
            "source": f"https://example.com/{name}",
            "bin": name,
            "format": archive_format,
            "platforms": {
                _PLATFORM: {
                    "url": f"https://example.com/releases/{name}",
                    "sha256": hashlib.sha256(artifact).hexdigest(),
                    "member": member,
                }
            },
        }
    )


def _python_entry() -> PythonTool:
    """A lock entry for a Semgrep installed from the packaged hashed requirements."""
    return PythonTool(
        version="9.9.9",
        description="Semgrep under test",
        source="https://example.com/semgrep",
        requirements="semgrep.txt",
        entry_points=["semgrep"],
    )


def _tool_requests(stub_web: StubWeb) -> list[str]:
    """The requests the stub received, leaving out the telemetry exporter's to its loopback
    collector, which a command may flush as it exits."""
    return [url for url in stub_web.requested if urlsplit(url).hostname != "localhost"]


def _link_at_pin(name: str, target_dir: Path) -> None:
    """Install the packaged lock's `name` as install-tools leaves it, without downloading it."""
    target_dir.mkdir(parents=True, exist_ok=True)
    for command, installed in installed_commands(name, load_tools_lock().tools()[name]).items():
        installed.parent.mkdir(parents=True, exist_ok=True)
        installed.write_bytes(EXECUTABLE)
        (target_dir / command).symlink_to(installed)


# ── Binary tools ──────────────────────────────────────────────────────────────


def test_a_verified_binary_is_pinned_and_linked_from_its_url_alone(
    stub_web: StubWeb, tmp_path: Path, isolate_user_data_root: Path
) -> None:
    """The lock's URL is the only request: no latest-release lookup and no checksum file. The
    verified binary lands in the tool's version directory and the target directory links to it."""
    stub_web.content(ASSET_URL, EXECUTABLE)
    target = tmp_path / "bin"

    install_binary("mytool", _binary_entry(EXECUTABLE), target)

    pinned = isolate_user_data_root / "tools" / "mytool" / "1.2.3" / "mytool"
    assert (
        _tool_requests(stub_web),
        (target / "mytool").is_symlink(),
        (target / "mytool").resolve(),
        pinned.read_bytes(),
        os.access(pinned, os.X_OK),
        sorted(path.name for path in pinned.parent.parent.iterdir()),
    ) == ([ASSET_URL], True, pinned, EXECUTABLE, True, ["1.2.3"])


def test_an_install_removes_the_tools_other_versions(
    stub_web: StubWeb, tmp_path: Path, isolate_user_data_root: Path
) -> None:
    """Once the command links the locked version, the version directory of an earlier pin goes,
    so a pin bump does not leave the old build or virtual environment behind."""
    stub_web.content(ASSET_URL, EXECUTABLE)
    earlier = isolate_user_data_root / "tools" / "mytool" / "1.0.0"
    earlier.mkdir(parents=True)
    (earlier / "mytool").write_bytes(b"the earlier pin")

    install_binary("mytool", _binary_entry(EXECUTABLE), tmp_path / "bin")

    assert [path.name for path in earlier.parent.iterdir()] == ["1.2.3"]


def test_a_build_whose_bytes_differ_from_the_lock_is_refused(
    stub_web: StubWeb, tmp_path: Path, isolate_user_data_root: Path
) -> None:
    """A mismatch names the tool and leaves no version directory, no staging directory and no
    link behind."""
    stub_web.content(ASSET_URL, b"tampered")
    target = tmp_path / "bin"

    with pytest.raises(ChecksumMismatchError, match="mytool"):
        install_binary("mytool", _binary_entry(EXECUTABLE), target)

    assert (
        list((isolate_user_data_root / "tools" / "mytool").iterdir()),
        os.path.lexists(target / "mytool"),
    ) == ([], False)


@pytest.mark.parametrize(
    ("archive_format", "artifact", "member"),
    [
        ("binary", EXECUTABLE, None),
        ("gzip", gzip.compress(EXECUTABLE), None),
        ("tar.gz", _tar_gz({"README.md": b"docs", "dist/mytool": EXECUTABLE}), "dist/mytool"),
    ],
    # The archives' gzip headers carry the time they were built, so the bytes cannot name a test
    # that each xdist worker collects alike.
    ids=["binary", "gzip", "tar.gz"],
)
def test_each_archive_format_unpacks_to_the_tool(
    stub_web: StubWeb,
    tmp_path: Path,
    isolate_user_data_root: Path,
    archive_format: str,
    artifact: bytes,
    member: str | None,
) -> None:
    """A bare binary, a gzip file and a tar.gz member all become the same executable."""
    stub_web.content(ASSET_URL, artifact)

    install_binary(
        "mytool",
        _binary_entry(artifact, archive_format=archive_format, member=member),
        tmp_path / "bin",
    )

    assert (tmp_path / "bin" / "mytool").read_bytes() == EXECUTABLE


def test_a_platform_the_lock_has_no_build_for_is_named(stub_web: StubWeb, tmp_path: Path) -> None:
    """A platform missing from the lock fails before any request, naming the tool and platform."""
    entry = _binary_entry(EXECUTABLE).model_copy(update={"platforms": {}})

    with pytest.raises(ToolExecutionError) as raised:
        install_binary("mytool", entry, tmp_path / "bin")

    assert (
        "mytool" in str(raised.value),
        _PLATFORM in str(raised.value),
        _tool_requests(stub_web),
    ) == (
        True,
        True,
        [],
    )


def test_verify_sha256_names_the_tool_on_a_mismatch() -> None:
    """The checksum check passes the locked digest and refuses any other."""
    _verify_sha256("mytool", EXECUTABLE, hashlib.sha256(EXECUTABLE).hexdigest())

    with pytest.raises(ChecksumMismatchError, match="SHA-256 checksum mismatch for 'mytool'"):
        _verify_sha256("mytool", b"hello", "deadbeef" * 8)


# ── Python tools ──────────────────────────────────────────────────────────────


def _record_uv(
    monkeypatch: pytest.MonkeyPatch, *, sync_fails: bool = False
) -> list[tuple[list[str], object]]:
    """Stand in for uv: `venv` makes the stage's bin directory, `pip sync` writes the entry point.
    Each call is recorded with the environment keys it keeps beyond the default ones."""
    calls: list[tuple[list[str], object]] = []

    def run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((cmd, kwargs.get("extra_allowed_env")))
        if cmd[:3] == ["uv", "--no-config", "venv"]:
            (Path(cmd[-1]) / "bin").mkdir(parents=True)
        elif sync_fails:
            return subprocess.CompletedProcess(cmd, 1, "", "  Hash mismatch for `rich==15.0.0`\n")
        else:
            (Path(cmd[cmd.index("-p") + 1]).parent / "semgrep").write_bytes(EXECUTABLE)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(install_tools, "run_subprocess", run)
    monkeypatch.setattr("shutil.which", lambda name, *args, **kwargs: f"/usr/bin/{name}")
    return calls


def test_a_python_tool_installs_its_hashed_requirements_into_a_relocatable_venv(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, isolate_user_data_root: Path
) -> None:
    """uv builds a relocatable environment beside the version directory, installs exactly the
    hashed requirements into it, and the environment becomes the version directory. Neither call
    reads a uv configuration file, and both keep the devcontainer's malware check, cache directory
    and link mode. The link replaces the Semgrep that `uv tool install` once put on PATH."""
    calls = _record_uv(monkeypatch)
    target = tmp_path / "bin"
    target.mkdir()
    (target / "semgrep").write_text("the uv tool's semgrep", encoding="utf-8")

    install_python_tool("semgrep", _python_entry(), target)

    stage = Path(calls[0][0][-1])
    pinned = isolate_user_data_root / "tools" / "semgrep" / "9.9.9"
    uv_env = {"UV_MALWARE_CHECK", "UV_CACHE_DIR", "UV_LINK_MODE"}
    assert (
        calls,
        stage.parent,
        stage.exists(),
        (target / "semgrep").resolve(),
        (target / "semgrep").read_bytes(),
    ) == (
        [
            (
                ["uv", "--no-config", "venv", "--relocatable", "--python", "3.14", str(stage)],
                uv_env,
            ),
            (
                [
                    "uv",
                    "--no-config",
                    "pip",
                    "sync",
                    "--require-hashes",
                    "-p",
                    str(stage / "bin" / "python"),
                    str(LOCK_DIR / "semgrep.txt"),
                ],
                uv_env,
            ),
        ],
        pinned.parent,
        False,
        pinned / "bin" / "semgrep",
        EXECUTABLE,
    )


def test_a_failed_python_install_leaves_no_stage_and_no_link(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, isolate_user_data_root: Path
) -> None:
    """A requirement uv refuses fails the install with uv's reason, removes the half-built
    environment and links nothing."""
    _record_uv(monkeypatch, sync_fails=True)

    with pytest.raises(ToolExecutionError, match=r"semgrep: Hash mismatch for `rich==15\.0\.0`"):
        install_python_tool("semgrep", _python_entry(), tmp_path / "bin")

    assert (
        list((isolate_user_data_root / "tools" / "semgrep").iterdir()),
        os.path.lexists(tmp_path / "bin" / "semgrep"),
    ) == ([], False)


# ── The command ───────────────────────────────────────────────────────────────


def test_only_missing_skips_a_tool_at_its_pin_and_reinstalls_one_linked_elsewhere(
    stub_web: StubWeb, tmp_path: Path
) -> None:
    """`--only-missing` installs a tool unless its command links to its locked version."""
    target = tmp_path / "bin"
    _link_at_pin("gitleaks", target)
    elsewhere = tmp_path / "elsewhere" / "osv-scanner"
    elsewhere.parent.mkdir()
    elsewhere.write_bytes(EXECUTABLE)
    (target / "osv-scanner").symlink_to(elsewhere)
    osv_url = load_tools_lock().binary["osv-scanner"].platforms[_PLATFORM].url

    for tool in ("gitleaks", "osv-scanner"):
        runner.invoke(
            install_tools_app, ["--tool", tool, "--only-missing", "--target-dir", str(target)]
        )

    assert _tool_requests(stub_web) == [osv_url]


def test_check_passes_only_when_every_tool_is_at_its_pin(
    stub_web: StubWeb, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`--check` makes no request, exits 0 with every tool at its pin, and exits 1 naming each
    tool that is not."""
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    target = tmp_path / "bin"
    names = list(load_tools_lock().tools())
    for name in names:
        if name not in ("k9s", "semgrep"):
            _link_at_pin(name, target)

    failing = runner.invoke(install_tools_app, ["--check", "--target-dir", str(target)])
    for name in ("k9s", "semgrep"):
        _link_at_pin(name, target)
    passing = runner.invoke(install_tools_app, ["--check", "--target-dir", str(target)])

    named = [name for name in names if f"{name} " in failing.output]
    assert (failing.exit_code, named, passing.exit_code, _tool_requests(stub_web)) == (
        1,
        ["k9s", "semgrep"],
        0,
        [],
    )


@pytest.mark.parametrize(
    ("served", "exit_code", "linked"),
    [(EXECUTABLE, 0, True), (b"tampered", 1, False)],
    ids=["verified", "tampered"],
)
def test_install_tools_exits_1_when_it_refuses_a_build(
    stub_web: StubWeb,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    served: bytes,
    exit_code: int,
    linked: bool,
) -> None:
    """A build refused for its checksum fails the command, so `install-tools && ...` stops there,
    and leaves no link."""
    stub_web.content(ASSET_URL, served)
    lock = ToolsLock(python_version="3.14", binary={"mytool": _binary_entry(EXECUTABLE)}, python={})
    monkeypatch.setattr(install_tools, "load_tools_lock", lambda: lock)
    target = tmp_path / "bin"

    result = runner.invoke(install_tools_app, ["--target-dir", str(target)])

    assert (result.exit_code, os.path.lexists(target / "mytool")) == (exit_code, linked)


def test_status_shows_each_pin_and_what_is_installed_without_a_request(
    stub_web: StubWeb, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`status` reads the lock and the target directory only."""
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    target = tmp_path / "bin"
    _link_at_pin("gitleaks", target)
    gitleaks = load_tools_lock().binary["gitleaks"]

    result = runner.invoke(install_tools_app, ["status", "--target-dir", str(target)])

    gitleaks_row = next(line for line in result.output.splitlines() if "gitleaks" in line)
    assert (
        result.exit_code,
        all(column in result.output for column in ("Pinned", "Installed")),
        gitleaks.version in gitleaks_row,
        "at pin" in gitleaks_row,
        "not installed" in result.output,
        _tool_requests(stub_web),
    ) == (0, True, True, True, True, [])


def test_version_is_no_longer_an_option(tmp_path: Path) -> None:
    """The lock is the only version source."""
    result = runner.invoke(
        install_tools_app, ["--version", "v1.0.0", "--target-dir", str(tmp_path)]
    )

    assert result.exit_code == 2


def test_an_unknown_tool_is_refused(tmp_path: Path) -> None:
    """`--tool` names a tool in the lock."""
    result = runner.invoke(
        install_tools_app, ["--tool", "unknown-tool", "--target-dir", str(tmp_path)]
    )

    assert result.exit_code == 1


def test_install_managed_tools_reports_one_line_per_tool(
    stub_web: StubWeb, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Post-create's installer installs every tool the lock holds, and one tool's failure is one
    warning line."""
    stub_web.content(ASSET_URL, EXECUTABLE)
    lock = ToolsLock(
        python_version="3.14",
        binary={
            "mytool": _binary_entry(EXECUTABLE),
            "broken": _binary_entry(EXECUTABLE, name="broken"),
        },
        python={},
    )
    monkeypatch.setattr(install_tools, "load_tools_lock", lambda: lock)

    actions = install_managed_tools(tmp_path / "bin")
    again = install_managed_tools(tmp_path / "bin")

    assert (len(actions), actions[0].startswith("Installed mytool 1.2.3 into"), again) == (
        2,
        True,
        [actions[1]],
    )
    assert actions[1].startswith("Warning: Failed to install broken (")


def test_artifact_rejects_unknown_fields() -> None:
    """A typo in the lock fails the load rather than being ignored."""
    with pytest.raises(ValueError, match="extra"):
        Artifact.model_validate({"url": ASSET_URL, "sha256": "00" * 32, "sha512": "00"})


# ── Download egress ───────────────────────────────────────────────────────────


def test_download_follows_an_https_redirect(stub_web: StubWeb) -> None:
    """A release asset redirected to another https URL is fetched from there."""
    stub_web.redirect("https://example.com/tool.tar.gz", "https://example.org/asset")
    stub_web.page("https://example.org/asset", "binary")

    assert (_download("https://example.com/tool.tar.gz"), stub_web.requested) == (
        b"binary",
        ["https://example.com/tool.tar.gz", "https://example.org/asset"],
    )


@pytest.mark.parametrize(
    "url", ["http://example.com/tool.tar.gz", "https://example.com/tool.tar.gz"]
)
def test_download_refuses_any_hop_that_is_not_https(stub_web: StubWeb, url: str) -> None:
    """An http first URL, or an https URL redirecting to http, is refused before that hop is sent."""
    stub_web.redirect("https://example.com/tool.tar.gz", "http://example.com/tool.tar.gz")
    stub_web.page("http://example.com/tool.tar.gz", "binary")

    with pytest.raises(ToolDownloadError, match="Only HTTPS"):
        _download(url)

    assert [hop for hop in stub_web.requested if hop.startswith("http://")] == []


def test_download_refuses_a_private_answer_whatever_the_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tool hosts are public: the flag that once widened this check no longer does."""
    from tests.web_fakes import record_connects, scripted_resolver

    monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", "true")
    scripted_resolver(monkeypatch, {"example.com": [["10.0.0.1"]]})
    recorder = record_connects(monkeypatch, [])

    with pytest.raises(SSRFBlockedError):
        _download("https://example.com/tool.tar.gz")

    assert recorder.dialled == []
