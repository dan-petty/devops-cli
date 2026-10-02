"""The GenAI semantic conventions that LLM spans are written against, pinned to one commit.

`semconv_genai.json` holds the conventions' current attribute keys, metric names and span
types, reduced from what weaver resolves at the commit its `source` names. A person rewrites
it with `refresh_genai_snapshot` (`devops telemetry semconv refresh`). The gate never runs
weaver: it reads the committed table through `find_unknown_genai_literals`.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from collections.abc import Collection, Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any, NamedTuple

import yaml

from devops_cli.config.constants import (
    CONST_GIT_COMMIT_SHA_PATTERN,
    CONST_MAX_ERROR_DETAIL_LENGTH,
    CONST_PERM_REPO_FILE,
    CONST_PYTHON_STRING_PREFIX_MAX_LENGTH,
    CONST_PYTHON_TEMPLATE_STRING_PREFIXES,
    CONST_SEMCONV_GENAI_GIT_URL,
    CONST_SEMCONV_GENAI_LITERAL_PATTERN,
    CONST_SEMCONV_GENAI_MODEL_DIR,
    CONST_SEMCONV_GENAI_REPO,
    CONST_SEMCONV_RESOLVED_REGISTRY_FILE,
    CONST_SEMCONV_WEAVER_BIN,
    CONST_SEMCONV_WEAVER_VERSION,
    CONST_URL_WEAVER_RELEASES,
)
from devops_cli.config.defaults import DEFAULT_SEMCONV_WEAVER_TIMEOUT_SECONDS
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions import (
    DependencyError,
    SubprocessError,
    TelemetryError,
    ValidationError,
)
from devops_cli.output.file_writer import write_text_file

GENAI_SNAPSHOT_PATH = Path(__file__).with_name("semconv_genai.json")


class GenaiLiteral(NamedTuple):
    """A quoted string in Python source whose text starts with the GenAI namespace."""

    path: Path
    line: int
    text: str
    dynamic: bool

    def __str__(self) -> str:
        reason = (
            "builds a GenAI name at run time"
            if self.dynamic
            else "is not a current GenAI attribute key or metric name"
        )
        return f"{self.path}:{self.line}: {self.text!r} {reason}"


def reduce_resolved_registry(resolved: Mapping[str, Any]) -> dict[str, Any]:
    """Reduce weaver's v2 resolved registry to current attribute keys, metric names and spans.

    Every attribute in the catalog counts: the registry's own and those of the registries it
    depends on that its signals reference, such as `server.address`. Deprecated attributes,
    metrics and spans are left out. Each span type keeps its kind and its required attributes.
    """
    catalog = resolved["attribute_catalog"]
    registry = resolved["registry"]
    spans = sorted(
        (span for span in registry["spans"] if not span.get("deprecated")),
        key=lambda span: str(span["type"]),
    )
    return {
        "attributes": sorted({attr["key"] for attr in catalog if not attr.get("deprecated")}),
        "metrics": sorted({m["name"] for m in registry["metrics"] if not m.get("deprecated")}),
        "spans": {
            span["type"]: {"kind": span["kind"], "required": _required_keys(span, catalog)}
            for span in spans
        },
    }


def _required_keys(span: Mapping[str, Any], catalog: Sequence[Mapping[str, Any]]) -> list[str]:
    """Keys of the attributes a span requires; conditional requirements do not count."""
    return sorted(
        {
            catalog[ref["base"]]["key"]
            for ref in span.get("attributes", [])
            if ref.get("requirement_level") == "required"
        }
    )


def render_genai_snapshot(snapshot: Mapping[str, Any]) -> str:
    """Serialize a snapshot identically every time: sorted keys, two-space indent, final newline."""
    return json.dumps(snapshot, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def load_genai_snapshot(path: Path = GENAI_SNAPSHOT_PATH) -> dict[str, Any]:
    """Read the committed snapshot."""
    snapshot: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return snapshot


def current_genai_names(snapshot: Mapping[str, Any]) -> frozenset[str]:
    """Names a GenAI string in the source may take: the snapshot's attribute keys and metrics."""
    return frozenset(snapshot["attributes"]) | frozenset(snapshot["metrics"])


def find_unknown_genai_literals(source_root: Path, known: Collection[str]) -> list[GenaiLiteral]:
    """Every quoted GenAI name in source_root's Python files that is not known, or is a template.

    The raw text is read, comments and docstrings included, so an old name left in prose
    fails as well. A string that starts with the namespace and is an f-string or t-string
    builds its key at run time, which no snapshot can check, so it always fails.
    """
    return [
        literal
        for path in sorted(source_root.rglob("*.py"))
        for literal in _genai_literals(path)
        if literal.dynamic or literal.text not in known
    ]


def _genai_literals(path: Path) -> Iterator[GenaiLiteral]:
    """Yield every quoted string in a file whose text starts with the GenAI namespace."""
    text = path.read_text(encoding="utf-8")
    for match in CONST_SEMCONV_GENAI_LITERAL_PATTERN.finditer(text):
        prefix = _string_prefix(text, match.start()).lower()
        yield GenaiLiteral(
            path=path,
            line=text.count("\n", 0, match.start()) + 1,
            text=match["text"],
            dynamic=any(char in CONST_PYTHON_TEMPLATE_STRING_PREFIXES for char in prefix),
        )


def _string_prefix(text: str, quote_at: int) -> str:
    """The letters right before an opening quote, such as `f` or `rf`.

    Read backwards from the quote rather than matched by the pattern: a pattern that starts
    with an optional prefix is tried at every position and made the scan ten times slower.
    """
    start = quote_at
    while (
        start > 0
        and quote_at - start < CONST_PYTHON_STRING_PREFIX_MAX_LENGTH
        and text[start - 1].isalpha()
    ):
        start -= 1
    return text[start:quote_at]


def weaver_package_argv(weaver: str, commit: str, output_dir: Path) -> list[str]:
    """The weaver call that resolves the GenAI registry at commit into output_dir.

    weaver 0.26.1 refuses to package without a resolved-registry URI. It lands only in the
    package manifest, which is not read, so it names the registry that was resolved.
    Diagnostics go to stdout as JSON, so a failure can be reported by its messages.
    """
    registry = f"{CONST_SEMCONV_GENAI_GIT_URL}@{commit}[{CONST_SEMCONV_GENAI_MODEL_DIR}]"
    return [
        weaver,
        "registry",
        "package",
        "--v2",
        "-r",
        registry,
        "--resolved-registry-uri",
        registry,
        "--diagnostic-format",
        "json",
        "--diagnostic-stdout",
        "-o",
        str(output_dir),
    ]


def refresh_genai_snapshot(
    commit: str,
    *,
    snapshot_path: Path = GENAI_SNAPSHOT_PATH,
    timeout: float = DEFAULT_SEMCONV_WEAVER_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Resolve the GenAI conventions at commit with weaver and rewrite the snapshot.

    The snapshot is written only once weaver has resolved the registry and the result has
    reduced. Any refusal before that leaves it as it was.
    """
    if not CONST_GIT_COMMIT_SHA_PATTERN.fullmatch(commit):
        raise ValidationError(
            "--commit takes a full 40-character lowercase hexadecimal commit SHA, "
            f"not {commit[:CONST_MAX_ERROR_DETAIL_LENGTH]!r}.",
            field="commit",
        )
    weaver = shutil.which(CONST_SEMCONV_WEAVER_BIN)
    if weaver is None:
        raise DependencyError(
            CONST_SEMCONV_WEAVER_BIN,
            install_hint=(
                f"Install weaver {CONST_SEMCONV_WEAVER_VERSION} from "
                f"{CONST_URL_WEAVER_RELEASES} and put it on PATH."
            ),
        )
    with tempfile.TemporaryDirectory(prefix="devops-semconv-") as work_dir:
        workspace = Path(work_dir)
        version = _weaver_version(weaver, workspace, timeout)
        package_dir = workspace / "package"
        _run_weaver(weaver_package_argv(weaver, commit, package_dir), workspace, timeout)
        reduced = _reduce_package(package_dir / CONST_SEMCONV_RESOLVED_REGISTRY_FILE)
    source = {"repo": CONST_SEMCONV_GENAI_REPO, "commit": commit, "weaver": version}
    snapshot = {"source": source, **reduced}
    write_text_file(snapshot_path, render_genai_snapshot(snapshot), mode=CONST_PERM_REPO_FILE)
    return snapshot


def _weaver_version(weaver: str, workspace: Path, timeout: float) -> str:
    """The version weaver reports, such as `0.26.1` from `weaver 0.26.1`."""
    words = _run_weaver([weaver, "--version"], workspace, timeout).split()
    if not words:
        raise SubprocessError("weaver --version printed nothing.", command=[weaver, "--version"])
    return words[-1]


def _run_weaver(argv: list[str], workspace: Path, timeout: float) -> str:
    """Run weaver inside workspace and return its standard output.

    weaver keeps its git clones under `~/.weaver` and finds `.weaver.toml` by walking up from
    its working directory, so its home and working directory are both the throwaway workspace.
    """
    try:
        proc = run_subprocess(
            argv, cwd=workspace, env={"HOME": str(workspace)}, timeout=timeout, quiet=True
        )
    except subprocess.TimeoutExpired as exc:
        raise SubprocessError(
            f"weaver did not finish within {timeout:g} s, so the snapshot is unchanged.",
            command=argv,
        ) from exc
    if proc.returncode != 0:
        raise SubprocessError(
            f"weaver exited {proc.returncode}, so the snapshot is unchanged: "
            f"{_weaver_failure(proc)}",
            command=argv,
        )
    return proc.stdout or ""


def _weaver_failure(proc: subprocess.CompletedProcess[str]) -> str:
    """weaver's diagnostic messages, or the tail of its output when they are not JSON."""
    try:
        messages = [str(item["diagnostic"]["message"]) for item in json.loads(proc.stdout)]
    except ValueError, TypeError, KeyError:
        messages = []
    output_tail = (proc.stderr or proc.stdout or "").strip()[-CONST_MAX_ERROR_DETAIL_LENGTH:]
    return ("; ".join(messages) or output_tail)[:CONST_MAX_ERROR_DETAIL_LENGTH]


def _reduce_package(resolved_path: Path) -> dict[str, Any]:
    """Read the resolved registry weaver wrote and reduce it."""
    try:
        return reduce_resolved_registry(yaml.safe_load(resolved_path.read_text(encoding="utf-8")))
    except (OSError, yaml.YAMLError) as exc:
        raise TelemetryError(
            f"weaver finished without a readable {resolved_path.name}, so the snapshot is "
            f"unchanged: {exc}"[:CONST_MAX_ERROR_DETAIL_LENGTH]
        ) from exc
    except (KeyError, TypeError, IndexError) as exc:
        raise TelemetryError(
            f"weaver's {resolved_path.name} is not a v2 resolved registry, so the snapshot "
            f"is unchanged: {type(exc).__name__} {exc}"[:CONST_MAX_ERROR_DETAIL_LENGTH]
        ) from exc
