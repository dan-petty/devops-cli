"""Syntax-aware structural AST diff provider with Difftastic integration and sensitive data redaction."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from devops_cli.config.commands import BIN_DIFFT, build_difft_cmd, build_git_diff_cmd
from devops_cli.config.constants import CONST_MAX_FILE_SIZE_BYTES
from devops_cli.core.process import run_subprocess
from devops_cli.core.repo import find_repo_root, resolve_safe_subpath
from devops_cli.telemetry.tracer import trace_span

_SECRET_PATTERNS = [
    re.compile(
        r"-----BEGIN [A-Z0-9_-]+ PRIVATE KEY-----[\s\S]+?-----END [A-Z0-9_-]+ PRIVATE KEY-----"
    ),
    re.compile(
        r"(?:api[_-]?key|auth[_-]?token|bearer|password|secret|client[_-]?secret)\s*[:=]\s*['\"]?([A-Za-z0-9_\-\.]{8,})['\"]?",
        re.IGNORECASE,
    ),
    re.compile(r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36}"),
    re.compile(r"sk-[A-Za-z0-9]{20,48}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
]


MAX_DIFF_TEXT_CHARS: int = 500_000


def sanitize_diff_output(diff_text: str) -> str:
    """Sanitize sensitive credentials, secrets, private keys, and tokens from diff output."""
    if not diff_text:
        return ""
    text = diff_text
    if len(text) > MAX_DIFF_TEXT_CHARS:
        text = (
            text[:MAX_DIFF_TEXT_CHARS]
            + f"\n... [Diff truncated at {MAX_DIFF_TEXT_CHARS} characters] ...\n"
        )
    sanitized = text
    for pat in _SECRET_PATTERNS:
        sanitized = pat.sub("[REDACTED_SECRET]", sanitized)
    from devops_cli.ai.review.sanitization import _mask_secrets_in_content

    return _mask_secrets_in_content(sanitized)


_GIT_REF_RE = re.compile(r"^[A-Za-z0-9_\-./]+$")


def get_structural_diff(
    path_a: Path | str,
    path_b: Path | str | None = None,
    branch: str | None = None,
    base: str | None = None,
    repo_root: Path | str | None = None,
) -> str:
    """Produce syntax-aware structural AST diff using Difftastic with git diff fallback."""
    with trace_span("diff.structural_ast_diff"):
        root = find_repo_root(repo_root) if repo_root else find_repo_root()

        # Fallback to git branch diff
        if branch and base:
            if (
                not _GIT_REF_RE.fullmatch(branch)
                or not _GIT_REF_RE.fullmatch(base)
                or branch.startswith("-")
                or base.startswith("-")
            ):
                return "Error: Invalid git reference; illegal characters or leading hyphens are forbidden."
            git_cmd = build_git_diff_cmd(branch=branch, base=base)
            git_res = run_subprocess(git_cmd, check=False, cwd=root)
            raw_out = (
                git_res.stdout
                if git_res.returncode == 0
                else (git_res.stdout or git_res.stderr or "")
            )
            return sanitize_diff_output(raw_out)

        if path_b is not None:
            # Validate path containment to prevent arbitrary file read / CWE-200
            p_a = resolve_safe_subpath(root, path_a)
            p_b = resolve_safe_subpath(root, path_b)

            # Validate file size constraints to prevent resource exhaustion / CWE-400
            if p_a.exists() and p_a.stat().st_size > CONST_MAX_FILE_SIZE_BYTES:
                return f"File {p_a.name} exceeds maximum allowed size for diff analysis."
            if p_b.exists() and p_b.stat().st_size > CONST_MAX_FILE_SIZE_BYTES:
                return f"File {p_b.name} exceeds maximum allowed size for diff analysis."

            has_difft = shutil.which(BIN_DIFFT) is not None
            if has_difft:
                cmd = build_difft_cmd(path_a=p_a, path_b=p_b)
                res = run_subprocess(cmd, check=False, cwd=root)
                if res.returncode == 0 and res.stdout.strip():
                    return sanitize_diff_output(res.stdout)

            if p_a.exists() and p_b.exists():
                from difflib import unified_diff

                lines_a = p_a.read_text(encoding="utf-8", errors="replace").splitlines(
                    keepends=True
                )
                lines_b = p_b.read_text(encoding="utf-8", errors="replace").splitlines(
                    keepends=True
                )
                diff = unified_diff(lines_a, lines_b, fromfile=str(p_a), tofile=str(p_b))
                return sanitize_diff_output("".join(diff))

        return ""
