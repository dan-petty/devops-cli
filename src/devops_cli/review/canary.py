"""Review tool version resolution and expected-output canary gate (#1143).

Runs each review tool at the project's declared language and platform versions and verifies
that its output on a canary fixture matches the recorded expected `(rule, line)` set before
its findings count in a review.
"""

from __future__ import annotations

import functools
import hashlib
import importlib.metadata
import json
import re
import shutil
import sys
import tempfile
import tomllib
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, NamedTuple

from devops_cli.config.commands import (
    BIN_BANDIT,
    BIN_KUBELINTER,
    BIN_MYPY,
    BIN_PLUTO,
    BIN_RUFF,
    BIN_SEMGREP,
)
from devops_cli.config.constants import (
    CONST_CANARY_DOCKERFILE_SOURCE,
    CONST_CANARY_EXPECTED_RESULTS,
    CONST_CANARY_MANIFEST_YAML,
    CONST_CANARY_PYTHON_SOURCE,
    CONST_CANARY_SEMGREP_PROBES_YAML,
    CONST_CANARY_TOOLS,
    CONST_REVIEW_CONFIG_FILE,
)
from devops_cli.core.process import run_subprocess

_PYTHON_VERSION_RE = re.compile(r"(?:py)?(\d+)\.?(\d+)")
_MYPY_ERROR_LINE_RE = re.compile(
    r"^[^:\n]+:(?P<line>\d+)(?::\d+)?: error: .+?\s+\[(?P<code>[^\]]+)\]\s*$"
)


class CanaryCacheKey(NamedTuple):
    """Cache key identifying a single tool canary configuration (#1143)."""

    tool: str
    version: str
    binary_sha: str
    language_version: str
    ruleset_digest: str


class CanaryResult(NamedTuple):
    """Outcome of evaluating a tool's output against its expected `(rule, line)` set."""

    tool: str
    passed: bool
    actual: frozenset[tuple[str, int]]
    expected: frozenset[tuple[str, int]]
    cache_key: CanaryCacheKey

    @property
    def status(self) -> str:
        """Return `'passed'` when the canary gate matched, otherwise `'canary-failed'`."""
        return "passed" if self.passed else "canary-failed"


_CANARY_CACHE: dict[CanaryCacheKey, CanaryResult] = {}


def clear_canary_cache() -> None:
    """Clear all cached canary results."""
    _CANARY_CACHE.clear()
    _load_locked_tool_versions.cache_clear()
    _hash_binary_path.cache_clear()


def get_canary_cache() -> dict[CanaryCacheKey, CanaryResult]:
    """Return a shallow copy of the active canary result cache."""
    return dict(_CANARY_CACHE)


# ── Project Version Resolution ───────────────────────────────────────────────


def _load_pyproject_toml(tree: Path | None) -> dict[str, Any]:
    """Read and parse `pyproject.toml` from `tree`, returning an empty dict when absent."""
    if tree is None:
        return {}
    candidate = tree / "pyproject.toml" if tree.is_dir() else tree.parent / "pyproject.toml"
    if not candidate.is_file():
        return {}
    try:
        return tomllib.loads(candidate.read_text(encoding="utf-8"))
    except OSError, tomllib.TOMLDecodeError:
        return {}


def parse_requires_python_target_version(requires_python: str | None) -> str | None:
    """Convert a `requires-python` specifier (e.g. `>=3.14`) to Ruff `--target-version` (`py314`)."""
    if not requires_python or not isinstance(requires_python, str):
        return None
    cleaned = requires_python.strip()
    if re.fullmatch(r"py\d{2,3}", cleaned):
        return cleaned
    match = _PYTHON_VERSION_RE.search(cleaned)
    if not match:
        return None
    return f"py{match.group(1)}{match.group(2)}"


def resolve_ruff_target_version(
    tree: Path | None = None,
    pyproject_data: Mapping[str, Any] | None = None,
) -> str | None:
    """Resolve Ruff target version (`pyXY`) from `[project].requires-python` in `pyproject.toml`."""
    data = pyproject_data if pyproject_data is not None else _load_pyproject_toml(tree)
    project_tbl = data.get("project")
    if not isinstance(project_tbl, Mapping):
        return None
    raw_req = project_tbl.get("requires-python")
    return parse_requires_python_target_version(raw_req if isinstance(raw_req, str) else None)


def resolve_mypy_python_version(
    tree: Path | None = None,
    pyproject_data: Mapping[str, Any] | None = None,
) -> str | None:
    """Resolve mypy `python_version` (`X.Y`) from `[tool.mypy].python_version` in `pyproject.toml`."""
    data = pyproject_data if pyproject_data is not None else _load_pyproject_toml(tree)
    tool_tbl = data.get("tool")
    if not isinstance(tool_tbl, Mapping):
        return None
    mypy_tbl = tool_tbl.get("mypy")
    if not isinstance(mypy_tbl, Mapping):
        return None
    raw_ver = mypy_tbl.get("python_version")
    if isinstance(raw_ver, (str, int, float)):
        ver_str = str(raw_ver).strip()
        if re.fullmatch(r"\d+\.\d+", ver_str):
            return ver_str
    return None


def normalize_kubernetes_version(raw_version: str | None) -> str | None:
    """Normalize a Kubernetes version string to Pluto's `vX.Y(.Z)` semver format."""
    if not raw_version or not isinstance(raw_version, str):
        return None
    cleaned = raw_version.strip()
    if not cleaned:
        return None
    if cleaned.startswith("k8s="):
        cleaned = cleaned.removeprefix("k8s=").strip()
    if not cleaned:
        return None
    return cleaned if cleaned.startswith("v") else f"v{cleaned}"


def resolve_review_kubernetes_version(
    review_config: Mapping[str, Any] | None = None,
    tree: Path | None = None,
) -> str | None:
    """Resolve `review.kubernetes_version` from `.devops/review.toml`."""
    cfg: Mapping[str, Any] = review_config or {}
    if not cfg and tree is not None:
        base = tree if tree.is_dir() else tree.parent
        cfg_path = base / CONST_REVIEW_CONFIG_FILE
        if cfg_path.is_file():
            try:
                cfg = tomllib.loads(cfg_path.read_text(encoding="utf-8"))
            except OSError, tomllib.TOMLDecodeError:
                cfg = {}

    raw = cfg.get("kubernetes_version")
    if not raw and isinstance(cfg.get("review"), Mapping):
        raw = cfg["review"].get("kubernetes_version")
    return normalize_kubernetes_version(raw if isinstance(raw, str) else None)


# ── Canary Output Parsers ────────────────────────────────────────────────────


def _load_json_dict(raw_output: str | Mapping[str, Any]) -> dict[str, Any]:
    """Coerce raw string or mapping output into a dictionary."""
    if isinstance(raw_output, Mapping):
        return dict(raw_output)
    if not isinstance(raw_output, str) or not raw_output.strip():
        return {}
    try:
        loaded = json.loads(raw_output)
        return loaded if isinstance(loaded, dict) else {}
    except json.JSONDecodeError:
        return {}


def _parse_semgrep_canary(raw_output: str | Mapping[str, Any]) -> frozenset[tuple[str, int]]:
    """Extract `(rule_id, line)` pairs from Semgrep JSON output."""
    payload = _load_json_dict(raw_output)
    pairs: set[tuple[str, int]] = set()
    for item in payload.get("results") or ():
        if not isinstance(item, Mapping):
            continue
        check_id = str(item.get("check_id") or "")
        rule_id = check_id.rsplit(".", 1)[-1] if "canary-pep758-" in check_id else check_id
        start = item.get("start")
        line = start.get("line") if isinstance(start, Mapping) else item.get("line")
        if rule_id and isinstance(line, int):
            pairs.add((rule_id, line))
    return frozenset(pairs)


def _parse_ruff_canary(raw_output: str | Mapping[str, Any]) -> frozenset[tuple[str, int]]:
    """Extract `(rule_id, line)` pairs from Ruff SARIF output."""
    payload = _load_json_dict(raw_output)
    runs = payload.get("runs")
    if not isinstance(runs, list) or not runs or not isinstance(runs[0], Mapping):
        return frozenset()
    pairs: set[tuple[str, int]] = set()
    for res in runs[0].get("results") or ():
        if not isinstance(res, Mapping):
            continue
        rule_id = str(res.get("ruleId") or "")
        locs = res.get("locations")
        line = None
        if isinstance(locs, list) and locs and isinstance(locs[0], Mapping):
            phys = locs[0].get("physicalLocation")
            if isinstance(phys, Mapping) and isinstance(phys.get("region"), Mapping):
                line = phys["region"].get("startLine")
        if rule_id and isinstance(line, int):
            pairs.add((rule_id, line))
    return frozenset(pairs)


def _parse_bandit_canary(raw_output: str | Mapping[str, Any]) -> frozenset[tuple[str, int]]:
    """Extract `(test_id, line_number)` pairs from Bandit JSON output."""
    payload = _load_json_dict(raw_output)
    pairs: set[tuple[str, int]] = set()
    for item in payload.get("results") or ():
        if not isinstance(item, Mapping):
            continue
        rule_id = str(item.get("test_id") or "")
        line = item.get("line_number")
        if rule_id and isinstance(line, int):
            pairs.add((rule_id, line))
    return frozenset(pairs)


def _parse_mypy_canary(raw_output: str | Mapping[str, Any]) -> frozenset[tuple[str, int]]:
    """Extract `(error_code, line)` pairs from mypy console output."""
    text = raw_output if isinstance(raw_output, str) else str(raw_output.get("output", ""))
    pairs: set[tuple[str, int]] = set()
    for raw_line in text.splitlines():
        match = _MYPY_ERROR_LINE_RE.match(raw_line.strip())
        if match:
            pairs.add((match.group("code"), int(match.group("line"))))
    return frozenset(pairs)


def _find_manifest_line(needle: str) -> int:
    """Find 1-indexed line of `needle` in `CONST_CANARY_MANIFEST_YAML`."""
    for idx, line in enumerate(CONST_CANARY_MANIFEST_YAML.splitlines(), start=1):
        if needle in line:
            return idx
    return 1


def _parse_kubelinter_canary(raw_output: str | Mapping[str, Any]) -> frozenset[tuple[str, int]]:
    """Extract `(check, line)` pairs from kube-linter JSON output."""
    payload = _load_json_dict(raw_output)
    pairs: set[tuple[str, int]] = set()
    for report in payload.get("Reports") or ():
        if not isinstance(report, Mapping):
            continue
        check = str(report.get("Check") or "")
        line = report.get("line")
        if not isinstance(line, int):
            line = _find_manifest_line(
                "privileged: true" if check == "privileged-container" else check
            )
        if check:
            pairs.add((check, line))
    return frozenset(pairs)


def _parse_pluto_canary(raw_output: str | Mapping[str, Any]) -> frozenset[tuple[str, int]]:
    """Extract `(api_version, line)` pairs from Pluto JSON output."""
    payload = _load_json_dict(raw_output)
    pairs: set[tuple[str, int]] = set()
    for item in payload.get("items") or ():
        if not isinstance(item, Mapping):
            continue
        raw_api = item.get("api")
        api: Mapping[str, Any] = raw_api if isinstance(raw_api, Mapping) else {}
        version = str(item.get("apiVersion") or api.get("version") or "")
        line = item.get("line")
        if not isinstance(line, int):
            line = _find_manifest_line(f"apiVersion: {version}") if version else 1
        if version:
            pairs.add((version, line))
    return frozenset(pairs)


_CANARY_OUTPUT_PARSERS: dict[
    str, Callable[[str | Mapping[str, Any]], frozenset[tuple[str, int]]]
] = {
    "semgrep": _parse_semgrep_canary,
    "ruff": _parse_ruff_canary,
    "bandit": _parse_bandit_canary,
    "mypy": _parse_mypy_canary,
    "kube-linter": _parse_kubelinter_canary,
    "pluto": _parse_pluto_canary,
}


def parse_canary_output(
    tool: str,
    raw_output: str | Mapping[str, Any],
) -> frozenset[tuple[str, int]]:
    """Parse raw canary output for `tool` into a frozenset of `(rule, line)` tuples."""
    parser = _CANARY_OUTPUT_PARSERS.get(tool.lower())
    if parser is None:
        return frozenset()
    return parser(raw_output)


# ── Canary Fixtures, Metadata & Execution ────────────────────────────────────


def materialize_canary_fixtures(workdir: Path) -> dict[str, Path]:
    """Write the canary Python, manifest, Dockerfile, and Semgrep probe fixtures into `workdir`."""
    workdir.mkdir(parents=True, exist_ok=True)
    files = {
        "python": workdir / "canary.py",
        "semgrep_probes": workdir / "semgrep_probes.yaml",
        "manifest": workdir / "manifest.yaml",
        "dockerfile": workdir / "Dockerfile",
    }
    files["python"].write_text(CONST_CANARY_PYTHON_SOURCE, encoding="utf-8")
    files["semgrep_probes"].write_text(CONST_CANARY_SEMGREP_PROBES_YAML, encoding="utf-8")
    files["manifest"].write_text(CONST_CANARY_MANIFEST_YAML, encoding="utf-8")
    files["dockerfile"].write_text(CONST_CANARY_DOCKERFILE_SOURCE, encoding="utf-8")
    return files


_TOOL_BINARIES: dict[str, str] = {
    "semgrep": BIN_SEMGREP,
    "ruff": BIN_RUFF,
    "bandit": BIN_BANDIT,
    "mypy": BIN_MYPY,
    "kube-linter": BIN_KUBELINTER,
    "pluto": BIN_PLUTO,
}


@functools.lru_cache(maxsize=1)
def _load_locked_tool_versions() -> dict[str, str]:
    """Load pinned tool versions from `src/devops_cli/tools_lock/tools.lock`."""
    lock_path = Path(__file__).resolve().parents[1] / "tools_lock" / "tools.lock"
    if not lock_path.is_file():
        return {}
    try:
        data = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    except OSError, tomllib.TOMLDecodeError:
        return {}
    versions: dict[str, str] = {}
    for section in ("binary", "python"):
        tbl = data.get(section)
        if isinstance(tbl, Mapping):
            for name, meta in tbl.items():
                if isinstance(meta, Mapping) and isinstance(meta.get("version"), str):
                    versions[name] = meta["version"]
    return versions


@functools.lru_cache(maxsize=32)
def _hash_binary_path(resolved_path: str) -> str:
    """Compute SHA-256 hex digest of a binary on disk."""
    try:
        return hashlib.sha256(Path(resolved_path).read_bytes()).hexdigest()
    except OSError:
        return "unavailable"


def _resolve_tool_version_and_sha(tool: str) -> tuple[str, str]:
    """Resolve installed version and binary SHA-256 for `tool`."""
    norm = tool.lower()
    locked = _load_locked_tool_versions()
    version = locked.get(norm, "")
    if not version:
        try:
            version = importlib.metadata.version(norm)
        except importlib.metadata.PackageNotFoundError:
            version = "unknown"

    bin_name = _TOOL_BINARIES.get(norm, norm)
    which_path = shutil.which(bin_name)
    if not which_path and norm in ("ruff", "bandit", "mypy"):
        candidate = Path(sys.executable).parent / bin_name
        if candidate.is_file():
            which_path = str(candidate)
    binary_sha = _hash_binary_path(str(Path(which_path).resolve())) if which_path else "unavailable"
    return version, binary_sha


def _default_ruleset_digest(tool: str) -> str:
    """Compute ruleset digest for `tool`'s canary probe configuration."""
    norm = tool.lower()
    payload = CONST_CANARY_SEMGREP_PROBES_YAML if norm == "semgrep" else f"{norm}:canary-v1"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _build_semgrep_canary_cmd(_workdir: Path, _lang_ver: str) -> list[str]:
    return [
        BIN_SEMGREP,
        "scan",
        "--json",
        "--quiet",
        "--metrics=off",
        "--config",
        "semgrep_probes.yaml",
        "canary.py",
    ]


def _build_ruff_canary_cmd(_workdir: Path, lang_ver: str) -> list[str]:
    target_ver = (
        lang_ver
        if lang_ver.startswith("py")
        else (parse_requires_python_target_version(lang_ver) or "py314")
    )
    ruff_bin = shutil.which(BIN_RUFF) or str(Path(sys.executable).parent / BIN_RUFF)
    return [
        ruff_bin,
        "check",
        "--isolated",
        "--output-format=sarif",
        f"--target-version={target_ver}",
        "--select=B006",
        "canary.py",
    ]


def _build_bandit_canary_cmd(_workdir: Path, _lang_ver: str) -> list[str]:
    bandit_bin = shutil.which(BIN_BANDIT) or str(Path(sys.executable).parent / BIN_BANDIT)
    return [
        bandit_bin,
        "--ignore-nosec",
        "-q",
        "--severity-level",
        "medium",
        "-f",
        "json",
        "canary.py",
    ]


def _build_mypy_canary_cmd(workdir: Path, lang_ver: str) -> list[str]:
    py_ver = lang_ver.removeprefix("py") if lang_ver else "3.14"
    if "." not in py_ver and len(py_ver) >= 2:
        py_ver = f"{py_ver[0]}.{py_ver[1:]}"
    return [
        sys.executable,
        "-I",
        "-m",
        "mypy",
        f"--python-version={py_ver}",
        "--no-error-summary",
        "--cache-dir",
        str(workdir / "mypy_cache"),
        "canary.py",
    ]


def _build_kubelinter_canary_cmd(_workdir: Path, _lang_ver: str) -> list[str]:
    return [
        BIN_KUBELINTER,
        "lint",
        "manifest.yaml",
        "--format",
        "json",
        "--include",
        "privileged-container",
        "--do-not-auto-add-defaults",
    ]


def _build_pluto_canary_cmd(_workdir: Path, lang_ver: str) -> list[str]:
    k8s_ver = normalize_kubernetes_version(lang_ver) or "v1.37.1"
    return [
        BIN_PLUTO,
        "detect",
        "manifest.yaml",
        "-o",
        "json",
        "--target-versions",
        f"k8s={k8s_ver}",
    ]


_CANARY_COMMAND_BUILDERS: dict[str, Callable[[Path, str], list[str]]] = {
    "semgrep": _build_semgrep_canary_cmd,
    "ruff": _build_ruff_canary_cmd,
    "bandit": _build_bandit_canary_cmd,
    "mypy": _build_mypy_canary_cmd,
    "kube-linter": _build_kubelinter_canary_cmd,
    "pluto": _build_pluto_canary_cmd,
}


def build_canary_command(
    tool: str,
    workdir: Path,
    *,
    language_version: str = "",
) -> list[str]:
    """Build the command line used to run `tool` on its canary fixture in `workdir`."""
    builder = _CANARY_COMMAND_BUILDERS.get(tool.lower())
    if builder is None:
        raise ValueError(f"Unsupported canary tool: {tool}")
    return builder(workdir, language_version)


def _run_live_canary_command(tool: str, cmd: list[str], workdir: Path) -> str:
    """Execute a canary command in `workdir` and return its raw output string."""
    proc = run_subprocess(cmd, cwd=workdir, check=False)
    if tool.lower() == "mypy":
        return (proc.stdout or "") + (proc.stderr or "")
    return proc.stdout or ""


def evaluate_canary_gate(
    tool: str,
    raw_output: str | Mapping[str, Any],
    *,
    cache_key: CanaryCacheKey | None = None,
) -> CanaryResult:
    """Evaluate `raw_output` for `tool` against `CONST_CANARY_EXPECTED_RESULTS`."""
    norm = tool.lower()
    expected = CONST_CANARY_EXPECTED_RESULTS.get(norm, frozenset())
    actual = parse_canary_output(norm, raw_output)
    passed = actual == expected and bool(expected)
    eff_key = cache_key or CanaryCacheKey(
        tool=norm,
        version="recorded",
        binary_sha="recorded",
        language_version="default",
        ruleset_digest=_default_ruleset_digest(norm),
    )
    return CanaryResult(
        tool=norm,
        passed=passed,
        actual=actual,
        expected=expected,
        cache_key=eff_key,
    )


def run_tool_canary(
    tool: str,
    *,
    version: str | None = None,
    binary_sha: str | None = None,
    language_version: str = "",
    ruleset_digest: str | None = None,
    runner: Callable[[str, list[str], Path], str | Mapping[str, Any]] | None = None,
    use_cache: bool = True,
) -> CanaryResult:
    """Run the canary for `tool` once per `(tool, version, binary_sha, language_version, ruleset_digest)`."""
    norm = tool.lower()
    det_ver, det_sha = _resolve_tool_version_and_sha(norm)
    eff_ver = version if version is not None else det_ver
    eff_sha = binary_sha if binary_sha is not None else det_sha
    eff_lang = language_version or "default"
    eff_digest = ruleset_digest if ruleset_digest is not None else _default_ruleset_digest(norm)

    key = CanaryCacheKey(
        tool=norm,
        version=eff_ver,
        binary_sha=eff_sha,
        language_version=eff_lang,
        ruleset_digest=eff_digest,
    )
    if use_cache and key in _CANARY_CACHE:
        return _CANARY_CACHE[key]

    with tempfile.TemporaryDirectory(prefix=f"devops-canary-{norm}-") as tmp_dir:
        workdir = Path(tmp_dir)
        materialize_canary_fixtures(workdir)
        cmd = build_canary_command(norm, workdir, language_version=language_version)
        eff_runner = runner or _run_live_canary_command
        raw_output = eff_runner(norm, cmd, workdir)

    result = evaluate_canary_gate(norm, raw_output, cache_key=key)
    if use_cache:
        _CANARY_CACHE[key] = result
    return result


__all__ = [
    "CONST_CANARY_TOOLS",
    "CanaryCacheKey",
    "CanaryResult",
    "build_canary_command",
    "clear_canary_cache",
    "evaluate_canary_gate",
    "get_canary_cache",
    "materialize_canary_fixtures",
    "normalize_kubernetes_version",
    "parse_canary_output",
    "parse_requires_python_target_version",
    "resolve_mypy_python_version",
    "resolve_review_kubernetes_version",
    "resolve_ruff_target_version",
    "run_tool_canary",
]
