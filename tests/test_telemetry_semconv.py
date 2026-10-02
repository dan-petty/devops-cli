"""The pinned GenAI semantic conventions: snapshot, reducer, refresh refusals and source scan."""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any, NoReturn

import pytest
import yaml
from typer.testing import CliRunner

import devops_cli
import devops_cli.telemetry.semconv as semconv
from devops_cli.commands.telemetry import app
from devops_cli.config.constants import CONST_GIT_COMMIT_SHA_PATTERN
from devops_cli.dry_run import set_dry_run
from devops_cli.telemetry.semconv import (
    GENAI_SNAPSHOT_PATH,
    current_genai_names,
    find_unknown_genai_literals,
    load_genai_snapshot,
    reduce_resolved_registry,
    render_genai_snapshot,
    weaver_package_argv,
)

# A trimmed resolved.yaml from a real weaver 0.26.1 run; its header says how it was made.
RESOLVED_FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "semconv"
    / "semantic-conventions-v1.44.0-resolved-trimmed.yaml"
)
# What the reducer keeps of it: no deprecated attribute, metric or span.
RESOLVED_FIXTURE_REDUCED = {
    "attributes": ["http.request.method", "server.address", "server.port", "url.full"],
    "metrics": ["http.client.request.duration"],
    "spans": {
        "http.client": {
            "kind": "client",
            "required": ["http.request.method", "server.address", "server.port", "url.full"],
        }
    },
}
PINNED_COMMIT = "b31e9e8ea26ac1c086d3313d474e31d7c3f391ae"
FAKE_WEAVER = "/opt/weaver/weaver"

runner = CliRunner()

WeaverStub = Callable[..., subprocess.CompletedProcess[str]]


def _refuse_subprocess(*args: Any, **kwargs: Any) -> NoReturn:
    raise AssertionError(f"a subprocess was started: {args!r}")


def _squashed(text: str) -> str:
    """Text without whitespace, so a console that wraps long words still matches."""
    return "".join(text.split())


def _weaver_stub(package: Callable[[list[str]], subprocess.CompletedProcess[str]]) -> WeaverStub:
    """A stand-in for run_subprocess: `weaver --version` answers, the package call runs `package`."""

    def run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if argv[1:] == ["--version"]:
            return subprocess.CompletedProcess(argv, 0, stdout="weaver 0.26.1\n", stderr="")
        return package(argv)

    return run


def _package_exits_1(argv: list[str]) -> subprocess.CompletedProcess[str]:
    diagnostics = [{"diagnostic": {"message": "Git error occurred while cloning"}}]
    return subprocess.CompletedProcess(argv, 1, stdout=json.dumps(diagnostics), stderr="")


def _package_times_out(argv: list[str]) -> subprocess.CompletedProcess[str]:
    raise subprocess.TimeoutExpired(argv, 300.0)


def _package_writes_fixture(argv: list[str]) -> subprocess.CompletedProcess[str]:
    output_dir = Path(argv[argv.index("-o") + 1])
    output_dir.mkdir(parents=True)
    shutil.copyfile(RESOLVED_FIXTURE, output_dir / "resolved.yaml")
    return subprocess.CompletedProcess(argv, 0, stdout="[]", stderr="")


@pytest.fixture
def snapshot_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the command at a copy of the committed snapshot."""
    copy = tmp_path / "semconv_genai.json"
    shutil.copyfile(GENAI_SNAPSHOT_PATH, copy)
    monkeypatch.setattr(semconv, "GENAI_SNAPSHOT_PATH", copy)
    return copy


def test_snapshot_pins_the_genai_conventions() -> None:
    """The committed snapshot names its source and holds the names the LLM spans write."""
    snapshot = load_genai_snapshot()
    source = snapshot["source"]
    attributes = set(snapshot["attributes"])
    inference = snapshot["spans"]["gen_ai.inference.client"]
    expected_attributes = {
        "gen_ai.provider.name",
        "gen_ai.response.time_to_first_chunk",
        "server.address",
    }

    assert (
        source["repo"],
        CONST_GIT_COMMIT_SHA_PATTERN.fullmatch(source["commit"]) is not None,
        bool(source["weaver"]),
        sorted(expected_attributes - attributes),
        "gen_ai.system" in attributes,
        "gen_ai.client.operation.duration" in snapshot["metrics"],
        inference["kind"],
        sorted({"gen_ai.operation.name", "gen_ai.provider.name"} - set(inference["required"])),
        GENAI_SNAPSHOT_PATH.read_text(encoding="utf-8") == render_genai_snapshot(snapshot),
        (snapshot["attributes"], snapshot["metrics"]),
    ) == (
        "open-telemetry/semantic-conventions-genai",
        True,
        True,
        [],
        False,
        True,
        "client",
        [],
        True,
        (sorted(attributes), sorted(snapshot["metrics"])),
    )


def _reversed_reduction(resolved: dict[str, Any]) -> dict[str, Any]:
    """Reduce a copy of `resolved` whose catalog, metrics and spans run in reverse order."""
    catalog = resolved["attribute_catalog"]
    last = len(catalog) - 1
    registry = resolved["registry"]
    spans = [
        span
        | {"attributes": [ref | {"base": last - ref["base"]} for ref in span.get("attributes", [])]}
        for span in reversed(registry["spans"])
    ]
    return reduce_resolved_registry(
        {
            "attribute_catalog": list(reversed(catalog)),
            "registry": registry | {"metrics": list(reversed(registry["metrics"])), "spans": spans},
        }
    )


def test_reducer_drops_deprecated_names_and_is_byte_stable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The fixture's deprecated attribute, metric and span are dropped, sorted, byte-stable.

    The fixture is already in key order, so it is also reduced with its catalog, metrics and
    spans reversed (span references remapped), which only a sorting reducer still matches.
    """
    monkeypatch.setattr(subprocess, "Popen", _refuse_subprocess)
    resolved = yaml.safe_load(RESOLVED_FIXTURE.read_text(encoding="utf-8"))
    deprecated_attributes = sorted(
        {attr["key"] for attr in resolved["attribute_catalog"] if attr.get("deprecated")}
    )
    deprecated_metrics = [m["name"] for m in resolved["registry"]["metrics"] if m.get("deprecated")]
    first, second = (reduce_resolved_registry(resolved) for _ in range(2))

    assert (deprecated_attributes, deprecated_metrics, first, _reversed_reduction(resolved)) == (
        ["gen_ai.usage.prompt_tokens"],
        ["gen_ai.client.operation.duration"],
        RESOLVED_FIXTURE_REDUCED,
        RESOLVED_FIXTURE_REDUCED,
    )
    assert render_genai_snapshot(first).encode() == render_genai_snapshot(second).encode()


@pytest.mark.parametrize(
    ("weaver_path", "commit", "package", "cause"),
    [
        pytest.param(
            None,
            PINNED_COMMIT,
            _package_writes_fixture,
            "Required dependency 'weaver' is not installed or not available in PATH. Install "
            "weaver 0.26.1 from https://github.com/open-telemetry/weaver/releases",
            id="weaver-not-on-path",
        ),
        pytest.param(
            FAKE_WEAVER,
            "main",
            _package_writes_fixture,
            "--commit takes a full 40-character lowercase hexadecimal commit SHA, not 'main'.",
            id="commit-not-a-sha",
        ),
        pytest.param(
            FAKE_WEAVER,
            PINNED_COMMIT,
            _package_exits_1,
            "weaver exited 1, so the snapshot is unchanged: Git error occurred while cloning",
            id="weaver-fails",
        ),
        pytest.param(
            FAKE_WEAVER,
            PINNED_COMMIT,
            _package_times_out,
            "weaver did not finish within 300 s, so the snapshot is unchanged.",
            id="weaver-times-out",
        ),
    ],
)
def test_refresh_refuses_and_leaves_the_snapshot_unchanged(
    monkeypatch: pytest.MonkeyPatch,
    snapshot_copy: Path,
    weaver_path: str | None,
    commit: str,
    package: Callable[[list[str]], subprocess.CompletedProcess[str]],
    cause: str,
) -> None:
    """Each refusal exits non-zero, names its cause and writes nothing."""
    before = snapshot_copy.read_bytes()
    monkeypatch.setattr(shutil, "which", lambda name: weaver_path)
    monkeypatch.setattr(semconv, "run_subprocess", _weaver_stub(package))

    result = runner.invoke(app, ["semconv", "refresh", "--commit", commit])

    assert (result.exit_code, _squashed(cause) in _squashed(result.output)) == (1, True), (
        result.output
    )
    assert snapshot_copy.read_bytes() == before


def test_refresh_rewrites_the_snapshot_from_weavers_package(
    monkeypatch: pytest.MonkeyPatch, snapshot_copy: Path
) -> None:
    """weaver runs from a throwaway home, and the reduced registry becomes the snapshot."""
    calls: list[tuple[list[str], dict[str, Any]]] = []
    package = _weaver_stub(_package_writes_fixture)

    def recording_run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append((argv, kwargs))
        return package(argv, **kwargs)

    monkeypatch.setattr(shutil, "which", lambda name: FAKE_WEAVER)
    monkeypatch.setattr(semconv, "run_subprocess", recording_run)

    result = runner.invoke(app, ["semconv", "refresh", "--commit", PINNED_COMMIT])

    (version_argv, version_kwargs), (package_argv, package_kwargs) = calls
    workspace = version_kwargs["cwd"]
    expected = {
        "source": {
            "repo": "open-telemetry/semantic-conventions-genai",
            "commit": PINNED_COMMIT,
            "weaver": "0.26.1",
        },
        **RESOLVED_FIXTURE_REDUCED,
    }
    assert (
        result.exit_code,
        version_argv,
        package_argv,
        (package_kwargs["cwd"], package_kwargs["env"], package_kwargs["timeout"]),
        workspace.exists(),
        snapshot_copy.read_text(encoding="utf-8"),
        "4 attributes, 1 metrics and 1 span types" in " ".join(result.output.split()),
    ) == (
        0,
        [FAKE_WEAVER, "--version"],
        weaver_package_argv(FAKE_WEAVER, PINNED_COMMIT, workspace / "package"),
        (workspace, {"HOME": str(workspace)}, 300.0),
        False,
        render_genai_snapshot(expected),
        True,
    )


def test_refresh_dry_run_runs_nothing(monkeypatch: pytest.MonkeyPatch, snapshot_copy: Path) -> None:
    """--dry-run shows the weaver call and starts nothing."""
    before = snapshot_copy.read_bytes()
    monkeypatch.setattr(semconv, "run_subprocess", _refuse_subprocess)
    set_dry_run(True)
    try:
        result = runner.invoke(app, ["semconv", "refresh", "--commit", PINNED_COMMIT])
    finally:
        set_dry_run(False)

    assert (result.exit_code, "refresh_semconv_snapshot" in result.output) == (0, True)
    assert snapshot_copy.read_bytes() == before


def test_source_uses_only_current_genai_names() -> None:
    """Every GenAI string under src/ is a current attribute key or metric name of the snapshot."""
    source_root = Path(devops_cli.__file__).parent
    known = current_genai_names(load_genai_snapshot())

    assert [str(literal) for literal in find_unknown_genai_literals(source_root, known)] == []


def test_scan_names_each_unknown_or_dynamic_genai_string(tmp_path: Path) -> None:
    """An old key, a key built at run time and an old key in a comment each fail with file:line."""
    module = tmp_path / "module.py"
    module.write_text(
        'KEY = "gen_ai.system"\n'
        "def key(x):\n"
        '    return f"gen_ai.{x}"\n'
        '# was "gen_ai.system"\n'
        'METRIC = "gen_ai.client.operation.duration"\n',
        encoding="utf-8",
    )
    (tmp_path / "current.py").write_text(
        'NAMES = ("gen_ai.client.operation.duration", rb"gen_ai.request.model")\n',
        encoding="utf-8",
    )
    known = current_genai_names(load_genai_snapshot())

    assert [str(literal) for literal in find_unknown_genai_literals(tmp_path, known)] == [
        f"{module}:1: 'gen_ai.system' is not a current GenAI attribute key or metric name",
        f"{module}:3: 'gen_ai.{{x}}' builds a GenAI name at run time",
        f"{module}:4: 'gen_ai.system' is not a current GenAI attribute key or metric name",
    ]
