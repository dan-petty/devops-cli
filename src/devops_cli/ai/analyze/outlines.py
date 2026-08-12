"""Pseudocode structural outline generation, complexity scoring, and file metadata analysis."""

from __future__ import annotations

import ast
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from devops_cli.ai.analyze.scanner import (
    _extract_file_dependencies,
    _extract_file_purpose,
    _extract_file_symbols,
    detect_language,
)
from devops_cli.ai.personas import (
    ANALYZE_PSEUDOCODE_SYSTEM_PROMPT,
    ANALYZE_PSEUDOCODE_TASK_PROMPT,
)
from devops_cli.models.ai import FileAnalysisMeta


def _is_import_or_docstring_line(line: str) -> bool:
    """Return True if line is an import statement, docstring delimiter, or canned prose."""
    s = line.strip().lower()
    if not s:
        return True
    if s.startswith(("import ", "from ", "require(", "include ", "#include", "use ")):
        return True
    if s.startswith(('"""', "'''", "/*", "*/", "<!--", "-->")):
        return True
    if any(
        phrase in s
        for phrase in (
            "here is a pseudocode",
            "here is the pseudocode",
            "the following is a pseudocode",
            "pseudocode outline",
            "structural outline",
            "this file defines",
            "this script executes",
        )
    ):
        return True
    return False


def _calculate_complexity_score(content: str, line_count: int, symbols: list[str]) -> str:
    """Calculate complexity rating: Low, Medium, High."""
    branches = len(
        re.findall(r"\b(if|elif|else|for|while|try|except|switch|case|catch)\b", content)
    )
    score = line_count + (branches * 5) + (len(symbols) * 3)
    if score > 200:
        return "High"
    if score > 60:
        return "Medium"
    return "Low"


def _get_last_updated(rel_path: str, repo_root: Path | None = None) -> str:
    """Get ISO timestamp of when file was last updated via git log or stat mtime."""
    if repo_root and repo_root.exists():
        from devops_cli.core.process import run_subprocess

        try:
            res = run_subprocess(
                ["git", "log", "-1", "--format=%cI", "--", rel_path],
                cwd=repo_root,
                quiet=True,
                timeout=5.0,
            )
            if res.returncode == 0 and res.stdout.strip():
                return str(res.stdout.strip())
        except Exception:
            pass

        full_p = repo_root / rel_path
        if full_p.exists():
            try:
                mtime = full_p.stat().st_mtime
                return datetime.fromtimestamp(mtime, tz=UTC).isoformat()
            except Exception:
                pass

    return datetime.now(UTC).isoformat()


def _extract_python_pseudocode_outline(content: str) -> list[str]:
    """Extract AST signatures and key statements directly from Python source code."""
    lines: list[str] = []
    try:
        tree = ast.parse(content)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = [a.arg for a in node.args.args if a.arg != "self"]
                args_str = ", ".join(args[:3])
                if len(node.args.args) > 3:
                    args_str += ", ..."
                ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
                lines.append(f"{node.name}({args_str}){ret}:")
                for stmt in node.body[:2]:
                    if isinstance(
                        stmt,
                        (ast.If, ast.For, ast.While, ast.Return, ast.Raise, ast.Assign, ast.Expr),
                    ):
                        try:
                            stmt_code = ast.unparse(stmt).splitlines()[0]
                            lines.append(f"    {stmt_code[:60]}")
                        except Exception:
                            pass
            elif isinstance(node, ast.ClassDef):
                bases = [ast.unparse(b) for b in node.bases]
                bases_str = f"({', '.join(bases)})" if bases else ""
                lines.append(f"class {node.name}{bases_str}:")
                for item in node.body[:2]:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        args = [a.arg for a in item.args.args if a.arg != "self"]
                        lines.append(f"    def {item.name}({', '.join(args[:2])}):")
    except Exception:
        pass

    return lines[:10]


def _generate_pseudocode(
    rel_path: str,
    content: str,
    lang: str,
    symbols: list[str],
    purpose: str,
    ai_client: Any | None = None,
) -> list[str]:
    """Generate a representative list of strings simplifying key elements and structure."""
    if ai_client is not None and content.strip():
        try:
            from devops_cli.models.ai import ChatMessage

            prompt = (
                f"File: '{rel_path}' ({lang})\n\n"
                f"Source code snippet:\n{content[:200000]}\n\n"
                f"{ANALYZE_PSEUDOCODE_TASK_PROMPT}"
            )
            response = ai_client.chat_messages(
                system_prompt=ANALYZE_PSEUDOCODE_SYSTEM_PROMPT,
                messages=[ChatMessage(role="user", content=prompt)],
            )
            clean_res = str(response).strip()
            if clean_res:
                raw_steps = [
                    re.sub(r"^\d+[\.\)]\s*|^[-*]\s*", "", line).strip()
                    for line in clean_res.splitlines()
                    if line.strip()
                ]
                filtered_steps = [s for s in raw_steps if s and not _is_import_or_docstring_line(s)]
                if filtered_steps:
                    return filtered_steps[:10]
        except Exception:
            pass

    if lang == "python" and content.strip():
        py_outline = _extract_python_pseudocode_outline(content)
        if py_outline:
            return py_outline

    if lang in ("json", "yaml", "toml") and content.strip():
        try:
            if lang == "json":
                data = json.loads(content)
                if isinstance(data, dict) and data:
                    out_steps: list[str] = []
                    for k, v in list(data.items())[:8]:
                        val_str = json.dumps(v)
                        if len(val_str) > 60:
                            val_str = val_str[:57] + "..."
                        out_steps.append(f"{k}: {val_str}")
                    if out_steps:
                        return out_steps
                elif isinstance(data, list) and data:
                    return [json.dumps(item)[:60] for item in data[:8]]
        except Exception:
            pass

    if lang in ("shell", "bash") and content.strip():
        non_comment_lines: list[str] = []
        for line in content.splitlines():
            line_str = line.strip()
            if line_str and not line_str.startswith("#"):
                non_comment_lines.append(line_str[:60])
                if len(non_comment_lines) >= 8:
                    break

        if non_comment_lines:
            return non_comment_lines

    first_line = content.strip().splitlines()[0][:80] if content.strip() else ""
    return [first_line] if first_line else []


def analyze_single_file(
    rel_path: str,
    content: str,
    size_bytes: int,
    change_type: str = "existing",
    enhanced: bool = True,
    repo_root: Path | None = None,
    ai_client: Any | None = None,
) -> FileAnalysisMeta:
    """Analyze a single file and construct a FileAnalysisMeta object."""
    line_count = len(content.splitlines()) if content else 0
    char_count = len(content)
    lang = detect_language(rel_path, content)
    symbols = _extract_file_symbols(content, lang)
    purpose = _extract_file_purpose(rel_path, content, lang, symbols)
    deps = _extract_file_dependencies(content, lang)

    pseudocode = None
    last_updated = None
    last_analyzed = None
    complexity = None

    if enhanced:
        last_updated = _get_last_updated(rel_path, repo_root)
        last_analyzed = datetime.now(UTC).isoformat()
        complexity = _calculate_complexity_score(content, line_count, symbols)
        pseudocode = _generate_pseudocode(
            rel_path, content, lang, symbols, purpose, ai_client=ai_client
        )

    return FileAnalysisMeta(
        path=rel_path,
        size_bytes=size_bytes,
        line_count=line_count,
        char_count=char_count,
        language=lang,
        primary_purpose=purpose,
        key_symbols=symbols,
        dependencies=deps,
        change_type=change_type,
        pseudocode=pseudocode,
        last_updated=last_updated,
        last_analyzed=last_analyzed,
        complexity_score=complexity,
    )
