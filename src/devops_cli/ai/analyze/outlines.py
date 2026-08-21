"""Pseudocode structural outline generation, complexity scoring, and file metadata analysis."""

from __future__ import annotations

import ast
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

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

_TASKS_DIR = Path(__file__).resolve().parent.parent / "tasks"


def _load_task_prompt(filename: str) -> str:
    path = _TASKS_DIR / filename
    return path.read_text(encoding="utf-8").strip() if path.exists() else ""


_METADATA_RETRY_TEMPLATE = _load_task_prompt("metadata_retry_feedback.md")


class EnhancedMetadataOutput(BaseModel):
    """Pydantic model for validating AI-generated metadata extraction."""

    primary_purpose: str = ""
    key_symbols: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    pseudocode: list[str] = Field(default_factory=list)
    complexity_score: Literal["Low", "Medium", "High"] = "Low"
    confidence_score: float = Field(default=0.85, ge=0.0, le=1.0)
    quality_score: float = Field(default=0.85, ge=0.0, le=1.0)


def _validate_enhanced_metadata(
    data: Any,
    has_content: bool,
    static_symbols: list[str],
) -> tuple[EnhancedMetadataOutput | None, str | None]:
    """Validate extracted AI metadata payload; return (parsed_output, error_reason)."""
    if not isinstance(data, dict):
        return None, "Output must be a JSON object dictionary."

    try:
        parsed = EnhancedMetadataOutput.model_validate(data)
    except Exception as exc:
        return None, f"Schema validation error: {exc}"

    if has_content and (not parsed.primary_purpose or len(parsed.primary_purpose.strip()) < 5):
        return None, "primary_purpose is missing or too short."

    if static_symbols and not isinstance(parsed.key_symbols, list):
        return None, "key_symbols must be a list of strings."

    if not (0.0 <= parsed.confidence_score <= 1.0):
        return None, "confidence_score must be between 0.0 and 1.0."

    if not (0.0 <= parsed.quality_score <= 1.0):
        return None, "quality_score must be between 0.0 and 1.0."

    return parsed, None


def _mask_sensitive_data(text: str) -> str:
    """Mask credentials and secrets before transmitting code to external LLM services."""
    masked = re.sub(
        r"(ghp_[A-Za-z0-9_]{36}|gho_[A-Za-z0-9_]{36}|github_pat_[A-Za-z0-9_]{82})",
        "<github-token-masked>",
        text,
    )
    masked = re.sub(r"(sk-[A-Za-z0-9_-]{20,})", "<ai-key-masked>", masked)
    masked = re.sub(
        r"-----BEGIN [A-Z ]+ PRIVATE KEY-----[\s\S]*?-----END [A-Z ]+ PRIVATE KEY-----",
        "<private-key-masked>",
        masked,
    )
    return masked


def _enhance_file_metadata_with_ai(
    rel_path: str,
    content: str,
    lang: str,
    static_symbols: list[str],
    ai_client: Any,
    max_retries: int = 2,
) -> EnhancedMetadataOutput | None:
    """Request AI metadata enhancement with JSON schema validation and retry logic."""
    from devops_cli.ai.personas import METADATA_SYSTEM_PROMPT
    from devops_cli.ai.review_schema import extract_json_block
    from devops_cli.models.ai import ChatMessage

    sanitized_content = _mask_sensitive_data(content[:150000])
    rag_context = ""
    try:
        from devops_cli.ai.rag.embeddings import EmbeddingsEngine
        from devops_cli.ai.rag.qdrant import QdrantClient
        from devops_cli.ai.rag.retriever import SemanticRetriever
        from devops_cli.config.settings import get_ai_api_key, load_settings

        settings = load_settings()
        if settings.ai.rag.enabled:
            qdrant = QdrantClient(
                base_url=settings.qdrant.url or "http://localhost:6333",
                allow_private_network=settings.ai.allow_private_network,
            )
            if qdrant.is_alive():
                embedder = EmbeddingsEngine(ai_config=settings.ai, api_key=get_ai_api_key(settings))
                retriever = SemanticRetriever(
                    qdrant=qdrant,
                    embedder=embedder,
                    code_collection=f"{settings.qdrant.collection_prefix}_code",
                    docs_collection=f"{settings.qdrant.collection_prefix}_docs",
                    default_top_k=2,
                )
                ctx = retriever.retrieve_context(
                    f"{rel_path} {' '.join(static_symbols[:5])}", top_k=2
                )
                if ctx.has_results:
                    rag_context = f"\n\nRelated Architectural Context:\n{ctx.formatted_text}\n"
    except Exception:
        pass

    prompt = (
        f"Analyze File: '{rel_path}' ({lang})\n\n"
        f"Source code excerpt:\n{sanitized_content}\n"
        f"{rag_context}\n"
        "Extract structured file metadata JSON strictly following system instructions."
    )
    messages = [ChatMessage(role="user", content=prompt)]

    for attempt in range(1, max_retries + 1):
        try:
            res_obj = ai_client.chat_messages(
                system_prompt=METADATA_SYSTEM_PROMPT,
                messages=messages,
            )
            raw_text = str(res_obj).strip()
            data = extract_json_block(raw_text)
            parsed, err = _validate_enhanced_metadata(data, bool(content.strip()), static_symbols)
            if parsed:
                return parsed

            if attempt < max_retries and err:
                messages.append(ChatMessage(role="assistant", content=raw_text))
                messages.append(
                    ChatMessage(
                        role="user",
                        content=_METADATA_RETRY_TEMPLATE.format(err=err),
                    )
                )
        except Exception:
            pass

    return None


def _calculate_file_confidence_score(
    content: str,
    purpose: str,
    symbols: list[str],
    deps: list[str],
    pseudocode: list[str] | None,
    ai_provided: bool = False,
) -> float:
    """Calculate dynamic confidence score based on metadata completeness and source context."""
    if not content.strip():
        return 0.50

    base = 0.50
    if purpose and len(purpose.strip()) > 10:
        base += 0.15
    if symbols:
        base += 0.10
    if deps:
        base += 0.05
    if pseudocode and len(pseudocode) >= 1:
        base += 0.10
    if ai_provided:
        base += 0.05

    return round(min(0.98, max(0.40, base)), 2)


def _calculate_file_quality_score(
    content: str,
    line_count: int,
    symbols: list[str],
    purpose: str,
    pseudocode: list[str] | None,
) -> float:
    """Calculate dynamic code quality score (0.0 to 1.0) based on design clarity and structure."""
    if not content.strip():
        return 0.50

    score = 0.50
    if any(
        line.strip().startswith(('"""', "'''", "//", "#", "/*", "<!--"))
        for line in content.splitlines()[:5]
    ):
        score += 0.15

    if symbols:
        score += 0.15

    if pseudocode and len(pseudocode) >= 3:
        score += 0.10

    if 10 <= line_count <= 500:
        score += 0.10
    elif line_count > 1500:
        score -= 0.10

    return round(min(0.98, max(0.30, score)), 2)


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
        rel_path_obj = Path(rel_path)
        if rel_path_obj.is_absolute() or ".." in rel_path_obj.parts:
            return datetime.now(UTC).isoformat()

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

        full_p = (repo_root / rel_path).resolve()
        if str(full_p).startswith(str(repo_root.resolve())) and full_p.exists():
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
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                args = [a.arg for a in node.args.args if a.arg != "self"]
                args_str = ", ".join(args[:3])
                if len(node.args.args) > 3:
                    args_str += ", ..."
                ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
                lines.append(f"{node.name}({args_str}){ret}:")
                for stmt in node.body[:2]:
                    if isinstance(
                        stmt,
                        ast.If
                        | ast.For
                        | ast.While
                        | ast.Return
                        | ast.Raise
                        | ast.Assign
                        | ast.Expr,
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
                    if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
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
    return [first_line] if first_line else [f"{Path(rel_path).name} structural entry point"]


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

    last_updated = _get_last_updated(rel_path, repo_root) if enhanced else None
    last_analyzed = datetime.now(UTC).isoformat() if enhanced else None
    complexity = _calculate_complexity_score(content, line_count, symbols) if enhanced else None

    ai_enhanced: EnhancedMetadataOutput | None = None
    if enhanced and ai_client is not None and content.strip():
        ai_enhanced = _enhance_file_metadata_with_ai(
            rel_path, content, lang, symbols, ai_client=ai_client
        )

    pseudocode: list[str] | None = None
    confidence_score: float | None = None
    quality_score: float | None = None

    if ai_enhanced:
        if ai_enhanced.primary_purpose and len(ai_enhanced.primary_purpose.strip()) > 5:
            purpose = ai_enhanced.primary_purpose
        if ai_enhanced.key_symbols:
            for s in ai_enhanced.key_symbols:
                if s and s not in symbols:
                    symbols.append(s)
        if ai_enhanced.dependencies:
            for d in ai_enhanced.dependencies:
                if d and d not in deps:
                    deps.append(d)
        if ai_enhanced.pseudocode:
            pseudocode = ai_enhanced.pseudocode[:10]
        else:
            pseudocode = _generate_pseudocode(
                rel_path, content, lang, symbols, purpose, ai_client=ai_client
            )
        complexity = ai_enhanced.complexity_score
        confidence_score = ai_enhanced.confidence_score
        quality_score = ai_enhanced.quality_score
    else:
        pseudocode = (
            _generate_pseudocode(rel_path, content, lang, symbols, purpose, ai_client=ai_client)
            if enhanced
            else None
        )
        confidence_score = (
            _calculate_file_confidence_score(
                content, purpose, symbols, deps, pseudocode, ai_provided=False
            )
            if enhanced
            else None
        )
        quality_score = (
            _calculate_file_quality_score(content, line_count, symbols, purpose, pseudocode)
            if enhanced
            else None
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
        confidence_score=confidence_score,
        quality_score=quality_score,
    )
