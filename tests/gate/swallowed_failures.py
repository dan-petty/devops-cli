"""Ratchet: swallowed failures (BLE001, S110, S112, unread check=False) may not grow (#1347).

Files under src/ may not exceed their recorded ceiling counts. When the count of a file falls,
the check fails until `--lower` lowers the ceiling to lock in the gain. The check is the
`swallowed-failures` row of `devops ci` (#2164): it runs Ruff over `src` once, and no pytest
worker runs it. #1336 turns each ratchet into a ban.
"""

from __future__ import annotations

import ast
import json
import shutil
import subprocess
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from tests.support.paths import FIXTURES, REPO_ROOT

CONST_SWALLOWED_FAILURES_RUFF_RULES: Final[tuple[str, ...]] = ("BLE001", "S110", "S112")
CONST_SWALLOWED_FAILURES_CHECK_ATTRS: Final[tuple[str, ...]] = ("returncode", "stdout", "stderr")

CONST_CEILINGS_FIXTURE: Final[Path] = FIXTURES / "swallowed_failures_ceilings.json"
CONST_LOWER_COMMAND: Final[str] = (
    'uv run python -c "import sys; from tests.gate.swallowed_failures import main; '
    "sys.exit(main(['--lower']))\""
)


@dataclass(frozen=True)
class SwallowedFailureSite:
    """A site where a failure is swallowed or uninspected."""

    path: str
    line: int
    rule: str
    message: str


def _resolve_ruff_binary() -> str:
    """Locate the ruff executable in the current environment or virtualenv."""
    venv_ruff = Path(sys.executable).parent / "ruff"
    if venv_ruff.is_file():
        return str(venv_ruff)
    system_ruff = shutil.which("ruff")
    return system_ruff if system_ruff else "ruff"


def collect_ruff_violations(target: Path, repo_root: Path) -> list[SwallowedFailureSite]:
    """Collect BLE001, S110, and S112 violations using ruff's own engine."""
    ruff_bin = _resolve_ruff_binary()
    rules_arg = ",".join(CONST_SWALLOWED_FAILURES_RUFF_RULES)
    proc = subprocess.run(
        [ruff_bin, "check", f"--select={rules_arg}", "--output-format=json", str(target)],
        capture_output=True,
        text=True,
        check=False,
    )
    if not proc.stdout.strip():
        return []
    return sites_from_ruff_items(json.loads(proc.stdout), repo_root)


def sites_from_ruff_items(
    items: Iterable[Mapping[str, Any]], repo_root: Path
) -> list[SwallowedFailureSite]:
    """Turn the findings of `ruff check --output-format=json` into sites."""
    sites: list[SwallowedFailureSite] = []
    for item in items:
        file_path = Path(item["filename"]).resolve()
        rel_path = (
            str(file_path.relative_to(repo_root))
            if file_path.is_relative_to(repo_root)
            else str(file_path)
        )
        sites.append(
            SwallowedFailureSite(
                path=rel_path,
                line=item["location"]["row"],
                rule=item["code"],
                message=item.get("message", ""),
            )
        )
    return sites


class _UnreadCheckFalseVisitor(ast.NodeVisitor):
    """AST visitor to find calls passing check=False whose result is never read."""

    def __init__(self, rel_path: str) -> None:
        self._rel_path = rel_path
        self._scopes: list[dict[str, _VarBinding]] = [{}]
        self.sites: list[SwallowedFailureSite] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._enter_and_exit_scope(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._enter_and_exit_scope(node)

    def _enter_and_exit_scope(self, node: ast.AST) -> None:
        self._scopes.append({})
        self.generic_visit(node)
        self._finalize_current_scope()
        self._scopes.pop()

    def _finalize_current_scope(self) -> None:
        current = self._scopes[-1]
        for binding in current.values():
            if not binding.read:
                for call in binding.calls:
                    self.sites.append(
                        SwallowedFailureSite(
                            path=self._rel_path,
                            line=call.lineno,
                            rule="check=False",
                            message="process call passing check=False whose result is never read",
                        )
                    )

    def visit_Expr(self, node: ast.Expr) -> None:
        call = _extract_check_false_call(node.value)
        if call is not None:
            self.sites.append(
                SwallowedFailureSite(
                    path=self._rel_path,
                    line=call.lineno,
                    rule="check=False",
                    message="process call passing check=False whose result is never read",
                )
            )
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        call = _extract_check_false_call(node.value)
        if call is not None:
            for target in node.targets:
                self._record_call_binding(target, call)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None:
            call = _extract_check_false_call(node.value)
            if call is not None:
                self._record_call_binding(node.target, call)
        self.generic_visit(node)

    def _record_call_binding(self, target: ast.AST, call: ast.Call) -> None:
        if isinstance(target, ast.Name):
            scope = self._scopes[-1]
            binding = scope.setdefault(target.id, _VarBinding())
            binding.calls.append(call)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if isinstance(node.value, ast.Name) and node.attr in CONST_SWALLOWED_FAILURES_CHECK_ATTRS:
            self._mark_name_as_read(node.value.id)
        self.generic_visit(node)

    def visit_Return(self, node: ast.Return) -> None:
        if node.value is not None:
            self._mark_names_in_tree_read(node.value)
        self.generic_visit(node)

    def visit_Yield(self, node: ast.Yield) -> None:
        if node.value is not None:
            self._mark_names_in_tree_read(node.value)
        self.generic_visit(node)

    def visit_YieldFrom(self, node: ast.YieldFrom) -> None:
        if node.value is not None:
            self._mark_names_in_tree_read(node.value)
        self.generic_visit(node)

    def _mark_names_in_tree_read(self, tree: ast.AST) -> None:
        for n in ast.walk(tree):
            if isinstance(n, ast.Name):
                self._mark_name_as_read(n.id)

    def _mark_name_as_read(self, name: str) -> None:
        for scope in reversed(self._scopes):
            if name in scope:
                scope[name].read = True


class _VarBinding:
    """Tracks calls bound to a variable and whether the result was read."""

    __slots__ = ("calls", "read")

    def __init__(self) -> None:
        self.calls: list[ast.Call] = []
        self.read: bool = False


def _is_check_false_call(node: ast.Call) -> bool:
    """Return True if any keyword is check=False."""
    return any(
        kw.arg == "check" and isinstance(kw.value, ast.Constant) and kw.value.value is False
        for kw in node.keywords
    )


def _extract_check_false_call(node: ast.AST) -> ast.Call | None:
    """Extract check=False call, unwrapping cast(...) wrappers."""
    if not isinstance(node, ast.Call):
        return None
    if _is_check_false_call(node):
        return node
    if (
        isinstance(node.func, ast.Name)
        and node.func.id == "cast"
        and len(node.args) >= 2
        and isinstance(node.args[1], ast.Call)
        and _is_check_false_call(node.args[1])
    ):
        return node.args[1]
    return None


def collect_ast_unread_check_false(
    target: Path,
    repo_root: Path,
    trees: Mapping[Path, ast.Module] | None = None,
) -> list[SwallowedFailureSite]:
    """Collect unread check=False process calls using Python AST parsing."""
    if trees is not None and not target.is_file():
        file_tree_pairs = [
            (p, tree) for p, tree in sorted(trees.items()) if p.is_relative_to(target)
        ]
    else:
        files = [target] if target.is_file() else sorted(target.rglob("*.py"))
        file_tree_pairs = []
        for f in files:
            if not f.name.endswith(".py"):
                continue
            try:
                tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
            except SyntaxError, UnicodeDecodeError:
                continue
            file_tree_pairs.append((f, tree))

    sites: list[SwallowedFailureSite] = []
    for f, tree in file_tree_pairs:
        rel = str(f.relative_to(repo_root)) if f.is_relative_to(repo_root) else str(f)
        visitor = _UnreadCheckFalseVisitor(rel)
        visitor.visit(tree)
        visitor._finalize_current_scope()
        sites.extend(visitor.sites)
    return sites


def collect_all_swallowed_failures(
    target: Path,
    repo_root: Path,
    trees: Mapping[Path, ast.Module] | None = None,
) -> dict[str, list[SwallowedFailureSite]]:
    """Group all swallowed failure sites across Ruff and AST checks by relative file path."""
    ruff_sites = collect_ruff_violations(target, repo_root)
    ast_sites = collect_ast_unread_check_false(target, repo_root, trees=trees)
    grouped: dict[str, list[SwallowedFailureSite]] = {}
    for site in [*ruff_sites, *ast_sites]:
        grouped.setdefault(site.path, []).append(site)
    return {k: grouped[k] for k in sorted(grouped)}


def load_ceilings(fixture_path: Path = CONST_CEILINGS_FIXTURE) -> dict[str, int]:
    """Load ceilings dictionary from fixture file."""
    if not fixture_path.exists():
        return {}
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def save_ceilings(fixture_path: Path, ceilings: dict[str, int]) -> None:
    """Save ceilings dictionary sorted with 2-space indentation."""
    sorted_dict = {k: ceilings[k] for k in sorted(ceilings) if ceilings[k] > 0}
    fixture_path.write_text(json.dumps(sorted_dict, indent=2) + "\n", encoding="utf-8")


def evaluate_ratchet(
    measured: dict[str, list[SwallowedFailureSite]],
    ceilings: dict[str, int],
) -> tuple[dict[str, list[SwallowedFailureSite]], dict[str, tuple[int, int]]]:
    """Return files exceeding their ceiling and files under their ceiling.

    Returns:
        (over_ceiling_failures, under_ceiling_reductions)
    """
    over_ceiling: dict[str, list[SwallowedFailureSite]] = {}
    under_ceiling: dict[str, tuple[int, int]] = {}

    all_paths = sorted({*measured.keys(), *ceilings.keys()})
    for path in all_paths:
        current_count = len(measured.get(path, []))
        ceiling = ceilings.get(path, 0)
        if current_count > ceiling:
            over_ceiling[path] = measured.get(path, [])
        elif current_count < ceiling:
            under_ceiling[path] = (current_count, ceiling)

    return over_ceiling, under_ceiling


def format_over_ceiling_error(over_ceiling: dict[str, list[SwallowedFailureSite]]) -> str:
    """Format diagnostic message listing each violation as file:line: rule."""
    lines = [f"Swallowed failures ratchet exceeded in {len(over_ceiling)} file(s):"]
    for path, sites in sorted(over_ceiling.items()):
        lines.append(f"  {path}: {len(sites)} site(s) found (ceiling exceeded):")
        for s in sites:
            lines.append(f"    {s.path}:{s.line}: {s.rule} ({s.message})")
    lines.append("Resolve or handle the failures properly; do not raise the ceiling.")
    return "\n".join(lines)


def format_under_ceiling_error(under_ceiling: dict[str, tuple[int, int]]) -> str:
    """Format error when files are under their ceiling, giving the command to lower it."""
    lines = [f"Swallowed failures ratchet improvement in {len(under_ceiling)} file(s):"]
    for path, (actual, ceiling) in sorted(under_ceiling.items()):
        lines.append(f"  {path}: count fell from {ceiling} to {actual}")
    lines.extend(
        [
            "Lock in this gain by updating the ceilings file:",
            f"  {CONST_LOWER_COMMAND}",
        ]
    )
    return "\n".join(lines)


def lower_ceilings(fixture_path: Path, repo_root: Path) -> dict[str, int]:
    """Recount and lower ceilings, deleting rows reaching 0, refusing if any count rose."""
    src_dir = repo_root / "src"
    measured = collect_all_swallowed_failures(src_dir, repo_root)
    existing = load_ceilings(fixture_path)
    over, under = evaluate_ratchet(measured, existing)
    if over:
        raise ValueError(
            f"Cannot lower ceilings: {len(over)} file(s) exceed their current ceiling!\n"
            + format_over_ceiling_error(over)
        )
    new_ceilings = dict(existing)
    for path, (actual, _) in under.items():
        if actual == 0:
            new_ceilings.pop(path, None)
        else:
            new_ceilings[path] = actual
    save_ceilings(fixture_path, new_ceilings)
    return new_ceilings


# ── Invariant Test ─────────────────────────────────────────────────────────────


def problems(repo_root: Path = REPO_ROOT, fixture: Path = CONST_CEILINGS_FIXTURE) -> list[str]:
    """Name the files over their ceiling and the files under it, for the sources in `src`."""
    measured = collect_all_swallowed_failures(repo_root / "src", repo_root)
    over, under = evaluate_ratchet(measured, load_ceilings(fixture))
    return [
        *([format_over_ceiling_error(over)] if over else []),
        *([format_under_ceiling_error(under)] if under else []),
    ]


def main(argv: list[str] | None = None) -> int:
    """Check the ratchet, or with `--lower` lower the ceilings to the counts of the sources."""
    args = sys.argv[1:] if argv is None else argv
    if "--lower" in args:
        try:
            lowered = lower_ceilings(CONST_CEILINGS_FIXTURE, REPO_ROOT)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        print(f"Successfully updated ceilings fixture ({len(lowered)} files remaining).")
        return 0
    found = problems()
    for line in found:
        print(line, file=sys.stderr)
    return 1 if found else 0
