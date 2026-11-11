"""The construct gate checks of the `constructs` row of `devops ci` (#1107, #1902, #2164).

The row scans `src` and `tests` with the ast-grep rules, and `ast-grep test` runs the cases of
each rule. These checks hold the rest of the gate:

- Each rule reports a violation in the tree that it holds, and reports none in the other tree.
- No committed file lets a construct past the gate: a changed `sgconfig.yml`, a rule with a
  waiver, a scan command that differs between the row and the hook, an ignore file that hides a
  source, or a missing ban of the hand-rolled address APIs.

The checks run as a row, so the scan runs once and not once for each pytest case.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final, NamedTuple

import pathspec
import yaml

from devops_cli.commands.ci import get_check_specs
from devops_cli.config.constants import (
    CONST_AST_GREP_SCAN_ARGS,
    CONST_AST_GREP_SCAN_ROOTS,
    CONST_GITIGNORE_FILENAME,
    CONST_GITIGNORE_PATTERN_STYLE,
)
from tests.gate.ruff_selection import names_rule, ruff_enforces
from tests.support.paths import REPO_ROOT

CONST_BANNED_HAND_ROLLED_APIS: Final[tuple[str, ...]] = (
    "socket.inet_aton",
    "socket.inet_ntoa",
    "socket.inet_pton",
    "socket.inet_ntop",
)
CONST_RUFF_PER_FILE_IGNORE_KEYS: Final[tuple[str, ...]] = (
    "per-file-ignores",
    "extend-per-file-ignores",
)
CONST_RUFF_SOURCE_SUFFIXES: Final[frozenset[str]] = frozenset({".py", ".pyi", ".ipynb"})
CONST_RUFF_IGNORE_FILE_NAMES: Final[frozenset[str]] = frozenset(
    {CONST_GITIGNORE_FILENAME, ".ignore"}
)
CONST_NET_CONSTRUCT_RULES: Final[tuple[str, ...]] = (
    "net-address-list",
    "net-bracket-affix",
    "net-cidr-build",
    "net-domain-list",
    "net-domain-suffix",
    "net-hostport",
    "net-ip-literal",
    "net-localhost-fallback",
    "net-normalise",
    "net-port-table",
    "net-pre-flight-resolve",
    "net-raw-http-client",
    "net-scheme-affix",
    "net-scheme-in",
    "net-url-build",
)
CONST_TEST_CONSTRUCT_RULES: Final[tuple[str, ...]] = (
    "test-elapsed-upper-bound",
    "test-function-has-assertion",
    "test-pytest-raises-checks-error",
)
# The hand-written CSS of the package, which reads only token variables (docs/DESIGN.md). The token
# CSS that Style Dictionary writes is beside the package module, outside this folder.
CONST_DESIGN_CSS_FILES: Final[tuple[str, ...]] = ("src/devops_cli/design/css/**",)
# The review and scanner packages, which take the working directory from the command layer (#2098).
CONST_REVIEW_CWD_READ_FILES: Final[tuple[str, ...]] = (
    "src/devops_cli/ai/review/**",
    "src/devops_cli/review/**",
    "src/devops_cli/security/**",
)
CONST_AST_GREP_RULE_FILES: Final[dict[str, tuple[str, ...]]] = {
    **dict.fromkeys(CONST_NET_CONSTRUCT_RULES, ("src/**",)),
    **dict.fromkeys(CONST_TEST_CONSTRUCT_RULES, ("tests/**",)),
    "review-cwd-read": CONST_REVIEW_CWD_READ_FILES,
    "css-color-literal": CONST_DESIGN_CSS_FILES,
}

_RULES_DIR = REPO_ROOT / ".ast-grep" / "rules"
_SCAN_TIMEOUT_SECONDS = 120
_GIT_TIMEOUT_SECONDS = 60
# The command layer reads the working directory one time and gives it down (#2098).
_COMMAND_LAYER = "src/devops_cli/commands"
# A tree that the `constructs` row scans and that the rule of the violation does not hold.
_OTHER_TREE = {
    "src": "tests",
    "tests": "src",
    "src/devops_cli/ai/review": _COMMAND_LAYER,
    "src/devops_cli/review": _COMMAND_LAYER,
    "src/devops_cli/security": _COMMAND_LAYER,
    "src/devops_cli/design/css": "src",
}
_CWD_READ = "from pathlib import Path\n\nroot = Path.cwd()\n"
_ELAPSED_UPPER_BOUND = (
    "import time\n\n\n"
    "def test_parse_is_fast():\n"
    "    start = time.perf_counter()\n"
    "    parse()\n"
    "    elapsed = time.perf_counter() - start\n"
    "    assert elapsed < 1.0\n"
)
_TEST_FUNCTION_HAS_NO_ASSERTION = "def test_missing_assertion():\n    compute()\n"
_TEST_PYTEST_RAISES_CHECKS_ONLY_TYPE = (
    "import pytest\n\n\ndef test_bare_raises():\n    with pytest.raises(Exception):\n"
    "        pass\n    assert True\n"
)


class Violation(NamedTuple):
    """One source that breaks one rule, the tree that the rule holds, and the suffix of the file
    that holds the source, which names its language."""

    rule: str
    tree: str
    source: str
    suffix: str = ".py"

    def scratch_file(self, number: int, *, twin: bool = False) -> str:
        """The scratch file of violation `number`: `v<n>` in the tree of the rule, or its twin
        `o<n>` in the other tree."""
        if twin:
            return f"{_OTHER_TREE[self.tree]}/o{number}{self.suffix}"
        return f"{self.tree}/v{number}{self.suffix}"


# One violation of each rule, and the tree that the rule holds.
VIOLATIONS: Final[tuple[Violation, ...]] = (
    Violation("net-port-table", "src", "port = 443 if tls else 80\n"),
    Violation("net-address-list", "src", 'bad_sans = ["localhost", "127.0.0.1"]\n'),
    Violation("net-scheme-in", "src", 'if "://" in url:\n    pass\n'),
    Violation("net-scheme-affix", "src", 'secure = url.startswith("https://")\n'),
    Violation("net-bracket-affix", "src", 'is_v6 = host.startswith("[") and ":" in host\n'),
    Violation("net-url-build", "src", 'url = f"http://{host}:{port}"\n'),
    Violation("net-domain-suffix", "src", 'inside = host.endswith(".example.com")\n'),
    Violation("net-domain-list", "src", 'LOCAL_DOMAINS = (".internal", ".home.arpa")\n'),
    Violation("net-normalise", "src", 'host = value.strip("[]")\n'),
    Violation("net-hostport", "src", 'host, _, port = endpoint.rpartition(":")\n'),
    Violation("net-ip-literal", "src", 'local = host == "127.0.0.1"\n'),
    Violation("net-localhost-fallback", "src", 'url = endpoint or "http://localhost:11434"\n'),
    Violation("net-cidr-build", "src", 'network = f"{ip}/32"\n'),
    Violation("net-pre-flight-resolve", "src", "ips = _resolve_host_ips(host)\n"),
    Violation("net-raw-http-client", "src", "client = httpx2.Client()\n"),
    Violation("test-elapsed-upper-bound", "tests", _ELAPSED_UPPER_BOUND),
    Violation("test-function-has-assertion", "tests", _TEST_FUNCTION_HAS_NO_ASSERTION),
    Violation("test-pytest-raises-checks-error", "tests", _TEST_PYTEST_RAISES_CHECKS_ONLY_TYPE),
    Violation("review-cwd-read", "src/devops_cli/ai/review", _CWD_READ),
    Violation("review-cwd-read", "src/devops_cli/review", _CWD_READ),
    Violation("review-cwd-read", "src/devops_cli/security", _CWD_READ),
    Violation("css-color-literal", "src/devops_cli/design/css", "a { color: #1c1c1a; }\n", ".css"),
)


def violation_table_problems(rules: Sequence[Mapping[str, Any]]) -> list[str]:
    """Name each rule that has no violation in the table, and each tree that a rule holds."""
    held: dict[str, list[str]] = {}
    for violation in VIOLATIONS:
        held.setdefault(violation.rule, []).append(f"{violation.tree}/**")
    expected = {rule["id"]: rule.get("files") for rule in rules}
    if held == expected:
        return []
    return [f"the violations hold {held}, and the rules hold {expected}"]


def scan_problems(reported: Mapping[str, set[str]]) -> list[str]:
    """Compare the rule ids reported for each scratch file with the table of violations.

    `reported` maps the name of a scratch file to the ids of the rules that reported it. A
    violation file `v<n>` must report its rule, and its twin `o<n>` in the other tree must not.
    """
    found: list[str] = []
    for number, violation in enumerate(VIOLATIONS):
        inside = violation.scratch_file(number)
        outside = violation.scratch_file(number, twin=True)
        if violation.rule not in reported.get(inside, set()):
            found.append(f"{violation.rule}: no report for a violation in {violation.tree}")
        if violation.rule in reported.get(outside, set()):
            found.append(f"{violation.rule}: reported in {_OTHER_TREE[violation.tree]}")
    return found


def _write_scratch(project: Path) -> None:
    """Write one violation file in its tree, and one in the other tree, for each table entry."""
    (project / "sgconfig.yml").write_text(
        yaml.safe_dump({"ruleDirs": [str(_RULES_DIR)]}), encoding="utf-8"
    )
    for number, violation in enumerate(VIOLATIONS):
        for name in (violation.scratch_file(number), violation.scratch_file(number, twin=True)):
            scratch = project / name
            scratch.parent.mkdir(parents=True, exist_ok=True)
            scratch.write_text(violation.source, encoding="utf-8")


def reported_rules(project: Path) -> dict[str, set[str]]:
    """Scan the scratch project once, as the `constructs` row scans its trees."""
    done = subprocess.run(
        ["ast-grep", "scan", "--json=compact", *CONST_AST_GREP_SCAN_ROOTS],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
        timeout=_SCAN_TIMEOUT_SECONDS,
    )
    reported: dict[str, set[str]] = {}
    for match in json.loads(done.stdout or "[]"):
        reported.setdefault(Path(match["file"]).as_posix(), set()).add(match["ruleId"])
    return reported


def _under(names: Sequence[str], roots: Sequence[str]) -> list[str]:
    """Pick the names that sit under one of the root directories."""
    return [name for name in names if any(name.startswith(f"{root}/") for root in roots)]


def _ignore_file_escapes(
    project: Path, covered: Sequence[Path], sources: Sequence[Path]
) -> list[str]:
    """Report an ignore file that drops a covered source from the walk of the construct gate.

    The root `.gitignore` is the project's own and stays, so only a source it matches is an
    escape; an ignore file under a covered root, or a root `.ignore`, is one by being there.
    """
    gitignore = project / CONST_GITIGNORE_FILENAME
    lines = gitignore.read_text(encoding="utf-8").splitlines() if gitignore.is_file() else []
    listed = pathspec.PathSpec.from_lines(CONST_GITIGNORE_PATTERN_STYLE, lines)
    nested = [
        f"{path.relative_to(project).as_posix()}: an ignore file under a covered root"
        for path in covered
        if path.name in CONST_RUFF_IGNORE_FILE_NAMES
    ]
    beside = [
        f"{name}: an ignore file beside pyproject.toml"
        for name in sorted(CONST_RUFF_IGNORE_FILE_NAMES - {CONST_GITIGNORE_FILENAME})
        if (project / name).exists()
    ]
    names = [path.relative_to(project).as_posix() for path in sources]
    matched = [
        f"{name}: matched by {CONST_GITIGNORE_FILENAME}"
        for name in names
        if listed.match_file(name)
    ]
    return [*nested, *beside, *matched]


def _sgconfig_escapes(project: Path, tracked: Sequence[str]) -> list[str]:
    """Report unlisted keys, modified ruleDirs, or extra sgconfig.yml files (#1107)."""
    sgconfig = project / "sgconfig.yml"
    if not sgconfig.is_file():
        return ["sgconfig.yml: missing"]
    try:
        raw = yaml.safe_load(sgconfig.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        return [f"[sgconfig.yml] malformed: {exc}"]
    unlisted = [
        f"[sgconfig.yml] {k}: outside the allowlist"
        for k in sorted(set(raw.keys()) - {"ruleDirs", "testConfigs"})
    ]
    rule_dirs = raw.get("ruleDirs")
    rule_dirs_escape = (
        []
        if rule_dirs == [".ast-grep/rules"]
        else [f"[sgconfig.yml] ruleDirs: {rule_dirs}, not ['.ast-grep/rules']"]
    )
    seconds = [
        f"{name}: a second sgconfig.yml"
        for name in sorted(tracked)
        if name != "sgconfig.yml" and Path(name).name == "sgconfig.yml"
    ]
    return [*unlisted, *rule_dirs_escape, *seconds]


def _rule_file_escapes(data: dict[str, Any], rid: str) -> list[str]:
    """Check rule properties: severity must be error, files must name the tree the rule holds,
    and ignores may not be set (#1902)."""
    escapes: list[str] = []
    if data.get("severity") != "error":
        escapes.append(f"[{rid}] severity: {data.get('severity')}, not error")
    files = list(CONST_AST_GREP_RULE_FILES.get(rid, ()))
    if files and data.get("files") != files:
        escapes.append(f"[{rid}] files: {data.get('files')}, not {files}")
    if "ignores" in data:
        escapes.append(f"[{rid}] ignores: outside the allowlist")
    return escapes


def _read_yaml_by_id(directory: Path) -> dict[str, dict[str, Any]]:
    """Read the YAML files of one directory, keyed by the `id` each one holds."""
    found: dict[str, dict[str, Any]] = {}
    for path in sorted(directory.glob("*.yml")) if directory.is_dir() else []:
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        ident = data.get("id")
        if isinstance(ident, str) and ident:
            found[ident] = data
    return found


def _rule_test_case_escapes(tests: dict[str, dict[str, Any]]) -> list[str]:
    """Verify each ast-grep rule has at least one valid and one invalid case."""
    escapes: list[str] = []
    for rid in sorted(CONST_AST_GREP_RULE_FILES):
        tdata = tests.get(rid)
        if not tdata or not tdata.get("valid"):
            escapes.append(f"[{rid}] has no valid case")
        if not tdata or not tdata.get("invalid"):
            escapes.append(f"[{rid}] has no invalid case")
    return escapes


def _ast_grep_rules_and_tests_escapes(project: Path) -> list[str]:
    """Report missing or unlisted ast-grep rules, severity/filter escapes, or missing test cases."""
    rules = _read_yaml_by_id(project / ".ast-grep" / "rules")
    rule_escapes = [esc for rid, data in rules.items() for esc in _rule_file_escapes(data, rid)]
    found_ids = set(rules)
    expected_ids = set(CONST_AST_GREP_RULE_FILES)
    id_escapes = [
        f"{rid}: missing from .ast-grep/rules" for rid in sorted(expected_ids - found_ids)
    ] + [f"[{rid}] outside CONST_AST_GREP_RULE_FILES" for rid in sorted(found_ids - expected_ids)]
    tests = _read_yaml_by_id(project / ".ast-grep" / "rule-tests")
    return [*id_escapes, *rule_escapes, *_rule_test_case_escapes(tests)]


def _pre_commit_scan_cmd_escapes(project: Path, expected_cmd: list[str]) -> list[str]:
    """Report whether the ast-grep-scan pre-commit hook runs the expected scan command."""
    pre_commit_file = project / ".pre-commit-config.yaml"
    if not pre_commit_file.is_file():
        return []
    try:
        cfg = yaml.safe_load(pre_commit_file.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        return [f"[.pre-commit-config.yaml] malformed: {exc}"]
    hooks = [h for r in cfg.get("repos", []) for h in r.get("hooks", [])]
    scan_hook = next((h for h in hooks if h.get("id") == "ast-grep-scan"), None)
    if scan_hook is None:
        return ["ast-grep-scan hook: missing from .pre-commit-config.yaml"]
    cmd = [*scan_hook.get("entry", "").split(), *scan_hook.get("args", [])]
    if cmd != expected_cmd:
        return [f"ast-grep-scan hook cmd: {cmd}, not {expected_cmd}"]
    return []


def _scan_command_escapes(project: Path) -> list[str]:
    """Report scan commands differing from CONST_AST_GREP_SCAN_ARGS in CI or pre-commit."""
    expected_cmd = ["uv", "run", "ast-grep", *CONST_AST_GREP_SCAN_ARGS]
    constructs = next((s for s in get_check_specs() if s.name == "constructs"), None)
    ci_escapes: list[str] = []
    if constructs is None:
        ci_escapes.append("constructs row: missing from get_check_specs()")
    elif constructs.cmd != expected_cmd:
        ci_escapes.append(f"constructs row cmd: {constructs.cmd}, not {expected_cmd}")
    return [*ci_escapes, *_pre_commit_scan_cmd_escapes(project, expected_cmd)]


def _tid251_escapes(lint: Mapping[str, Any]) -> list[str]:
    """Report unenforced TID251, per-file waivers of TID251, or missing banned socket APIs."""
    select = [*lint.get("select", []), *lint.get("extend-select", [])]
    ignore = [*lint.get("ignore", []), *lint.get("extend-ignore", [])]
    rule = "TID251"
    escapes: list[str] = []
    if rule not in select or not ruff_enforces(rule, select, ignore):
        escapes.append(f"{rule}: not enforced")
    for table in CONST_RUFF_PER_FILE_IGNORE_KEYS:
        for pattern, codes in lint.get(table, {}).items():
            if any(names_rule(rule, code) for code in codes):
                escapes.append(f"[tool.ruff.lint.{table}] {pattern}: waives {rule}")
    banned = lint.get("flake8-tidy-imports", {}).get("banned-api", {})
    for api in sorted(CONST_BANNED_HAND_ROLLED_APIS):
        if api not in banned:
            escapes.append(f"{api}: missing from flake8-tidy-imports.banned-api")
    return escapes


def construct_gate_escapes(
    pyproject: Mapping[str, Any], project: Path, tracked: Sequence[str]
) -> list[str]:
    """Report every way a committed file lets a construct past the ast-grep gate (#1107, #1902).

    `tracked` names the files that git tracks under `project`, so an untracked scratch file
    hides nothing and holds nothing.
    """
    lint = pyproject.get("tool", {}).get("ruff", {}).get("lint", {})
    covered = [project / name for name in _under(tracked, CONST_AST_GREP_SCAN_ROOTS)]
    sources = [p for p in covered if p.suffix in CONST_RUFF_SOURCE_SUFFIXES]
    return [
        *_sgconfig_escapes(project, tracked),
        *_ast_grep_rules_and_tests_escapes(project),
        *_scan_command_escapes(project),
        *_ignore_file_escapes(project, covered, sources),
        *_tid251_escapes(lint),
    ]


def tracked_files(project: Path) -> list[str]:
    """Name the files that git tracks under `project`; a git failure raises."""
    done = subprocess.run(
        ["git", "-C", str(project), "ls-files", "-z"],
        capture_output=True,
        text=True,
        check=True,
        timeout=_GIT_TIMEOUT_SECONDS,
    )
    return [name for name in done.stdout.split("\0") if name]


def problems(project: Path = REPO_ROOT) -> list[str]:
    """Every way the construct gate of `project` fails."""
    rules = [yaml.safe_load(path.read_text(encoding="utf-8")) for path in _RULES_DIR.glob("*.yml")]
    with tempfile.TemporaryDirectory() as scratch:
        _write_scratch(Path(scratch))
        scan = scan_problems(reported_rules(Path(scratch)))
    pyproject = tomllib.loads((project / "pyproject.toml").read_text(encoding="utf-8"))
    return [
        *violation_table_problems(rules),
        *scan,
        *construct_gate_escapes(pyproject, project, tracked_files(project)),
    ]


def main(argv: list[str] | None = None) -> int:
    """Print each problem and return 1 when there is one."""
    found = problems()
    for line in found:
        print(f"construct gate: {line}", file=sys.stderr)
    return 1 if found else 0
