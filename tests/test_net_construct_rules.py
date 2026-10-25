"""Tests for the ast-grep construct rules and the banned socket APIs (#1107, #1902)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import yaml

from devops_cli.commands.ci import get_check_spec
from devops_cli.config.constants import (
    CONST_AST_GREP_SCAN_ARGS,
)
from tests.support.paths import REPO_ROOT

CONST_BANNED_HAND_ROLLED_APIS: tuple[str, ...] = (
    "socket.inet_aton",
    "socket.inet_ntoa",
    "socket.inet_pton",
    "socket.inet_ntop",
)

pytestmark = pytest.mark.live("ast-grep", "ruff")

_RULES_DIR = REPO_ROOT / ".ast-grep" / "rules"
# The command layer reads the working directory one time and gives it down (#2098).
_COMMAND_LAYER = "src/devops_cli/commands"
# A tree that the `constructs` row scans and that the rule of the violation does not hold.
_OTHER_TREE = {
    "src": "tests",
    "tests": "src",
    "src/devops_cli/ai/review": _COMMAND_LAYER,
    "src/devops_cli/review": _COMMAND_LAYER,
    "src/devops_cli/security": _COMMAND_LAYER,
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

# One violation of each rule, and the tree that the rule holds.
_VIOLATIONS = [
    pytest.param("net-port-table", "src", "port = 443 if tls else 80\n", id="net-port-table"),
    pytest.param(
        "net-address-list", "src", 'bad_sans = ["localhost", "127.0.0.1"]\n', id="net-address-list"
    ),
    pytest.param("net-scheme-in", "src", 'if "://" in url:\n    pass\n', id="net-scheme-in"),
    pytest.param(
        "net-scheme-affix", "src", 'secure = url.startswith("https://")\n', id="net-scheme-affix"
    ),
    pytest.param(
        "net-bracket-affix",
        "src",
        'is_v6 = host.startswith("[") and ":" in host\n',
        id="net-bracket-affix",
    ),
    pytest.param("net-url-build", "src", 'url = f"http://{host}:{port}"\n', id="net-url-build"),
    pytest.param(
        "net-domain-suffix",
        "src",
        'inside = host.endswith(".example.com")\n',
        id="net-domain-suffix",
    ),
    pytest.param(
        "net-domain-list",
        "src",
        'LOCAL_DOMAINS = (".internal", ".home.arpa")\n',
        id="net-domain-list",
    ),
    pytest.param("net-normalise", "src", 'host = value.strip("[]")\n', id="net-normalise"),
    pytest.param(
        "net-hostport", "src", 'host, _, port = endpoint.rpartition(":")\n', id="net-hostport"
    ),
    pytest.param("net-ip-literal", "src", 'local = host == "127.0.0.1"\n', id="net-ip-literal"),
    pytest.param(
        "net-localhost-fallback",
        "src",
        'url = endpoint or "http://localhost:11434"\n',
        id="net-localhost-fallback",
    ),
    pytest.param("net-cidr-build", "src", 'network = f"{ip}/32"\n', id="net-cidr-build"),
    pytest.param(
        "test-elapsed-upper-bound", "tests", _ELAPSED_UPPER_BOUND, id="test-elapsed-upper-bound"
    ),
    pytest.param(
        "review-cwd-read", "src/devops_cli/ai/review", _CWD_READ, id="review-cwd-read-ai-review"
    ),
    pytest.param(
        "review-cwd-read", "src/devops_cli/review", _CWD_READ, id="review-cwd-read-review"
    ),
    pytest.param(
        "review-cwd-read", "src/devops_cli/security", _CWD_READ, id="review-cwd-read-security"
    ),
]


def _reported_rules(project: Path, tree: str, source: str) -> tuple[int, set[str]]:
    """Scan one new file in `tree` of a project that reads the repository's rules, as the
    `constructs` row scans its trees, and return the exit code and the ids of the rules reported."""
    (project / "sgconfig.yml").write_text(
        yaml.safe_dump({"ruleDirs": [str(_RULES_DIR)]}), encoding="utf-8"
    )
    scratch = project / tree / "test_scratch.py"
    scratch.parent.mkdir(parents=True, exist_ok=True)
    scratch.write_text(source, encoding="utf-8")
    res = subprocess.run(
        ["ast-grep", "scan", "--json=compact", tree],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )
    return res.returncode, {match["ruleId"] for match in json.loads(res.stdout or "[]")}


def test_ast_grep_rule_tests_pass() -> None:
    """Every rule in .ast-grep/rules/ has unit tests that pass with ast-grep test."""
    res = subprocess.run(
        ["ast-grep", "test", "--skip-snapshot-tests"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"ast-grep test failed:\nstdout: {res.stdout}\nstderr: {res.stderr}"


def test_the_violations_name_every_rule_and_the_tree_it_holds() -> None:
    """The scan tests below hold one violation of each rule in each tree that its `files` name."""
    rules = [yaml.safe_load(path.read_text(encoding="utf-8")) for path in _RULES_DIR.glob("*.yml")]
    held: dict[str, list[str]] = {}
    for param in _VIOLATIONS:
        held.setdefault(param.values[0], []).append(f"{param.values[1]}/**")

    assert held == {rule["id"]: rule.get("files") for rule in rules}


@pytest.mark.parametrize(("rule", "tree", "source"), _VIOLATIONS)
def test_ast_grep_scan_reports_a_new_violation_in_the_tree_its_rule_holds(
    tmp_path: Path, rule: str, tree: str, source: str
) -> None:
    """A new file with a violation fails the scan, and the scan names the rule (#1107, #1902)."""
    returncode, reported = _reported_rules(tmp_path, tree, source)

    assert (returncode != 0, rule in reported) == (True, True)


@pytest.mark.parametrize(("rule", "tree", "source"), _VIOLATIONS)
def test_ast_grep_scan_leaves_a_violation_in_the_other_tree_to_that_tree(
    tmp_path: Path, rule: str, tree: str, source: str
) -> None:
    """A rule holds only its own tree: tests hold literal addresses, and src holds no test (#1902)."""
    _, reported = _reported_rules(tmp_path, _OTHER_TREE[tree], source)

    assert rule not in reported


def test_ruff_tid251_detects_banned_socket_apis(tmp_path: Path) -> None:
    """Ruff TID251 flags banned socket.inet_* APIs in source code."""
    scratch = tmp_path / "scratch.py"
    scratch.write_text(
        "import socket\nfrom socket import inet_pton\nsocket.inet_aton('127.0.0.1')\n",
        encoding="utf-8",
    )

    res = subprocess.run(
        ["ruff", "check", "--select", "TID251", str(scratch)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode != 0
    output = res.stdout + res.stderr
    assert "TID251" in output
    assert "Parse and format addresses with ipaddress.ip_address." in output
    assert "socket.inet_aton" in output
    assert "socket.inet_pton" in output


def test_ci_constructs_row_matches_constants() -> None:
    """The constructs row in devops ci runs the scan with CONST_AST_GREP_SCAN_ARGS."""
    spec = get_check_spec("constructs")
    assert spec.cmd == ["uv", "run", "ast-grep", *CONST_AST_GREP_SCAN_ARGS]
    assert len(CONST_BANNED_HAND_ROLLED_APIS) == 4
