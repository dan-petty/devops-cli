"""Syntax-aware structural AST diff provider with Difftastic integration."""

from __future__ import annotations

import shutil
from pathlib import Path

from devops_cli.config.commands import BIN_DIFFT, build_difft_cmd, build_git_diff_cmd
from devops_cli.core.process import run_subprocess
from devops_cli.telemetry.tracer import trace_span


def get_structural_diff(
    path_a: Path | str,
    path_b: Path | str | None = None,
    branch: str | None = None,
    base: str | None = None,
) -> str:
    """Produce syntax-aware structural AST diff using Difftastic with git diff fallback."""
    with trace_span("diff.structural_ast_diff"):
        has_difft = shutil.which(BIN_DIFFT) is not None
        if has_difft and path_b is not None:
            cmd = build_difft_cmd(path_a=path_a, path_b=path_b)
            res = run_subprocess(cmd, check=False)
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout

        # Fallback to git diff
        if branch and base:
            git_cmd = build_git_diff_cmd(branch=branch, base=base)
            git_res = run_subprocess(git_cmd, check=False)
            return git_res.stdout

        if path_b is not None:
            p_a = Path(path_a)
            p_b = Path(path_b)
            if p_a.exists() and p_b.exists():
                from difflib import unified_diff

                lines_a = p_a.read_text(encoding="utf-8", errors="replace").splitlines(
                    keepends=True
                )
                lines_b = p_b.read_text(encoding="utf-8", errors="replace").splitlines(
                    keepends=True
                )
                diff = unified_diff(lines_a, lines_b, fromfile=str(p_a), tofile=str(p_b))
                return "".join(diff)

        return ""
