"""Codebase metadata analysis commands (branch, pr, path)."""

from __future__ import annotations

import ast
import fnmatch
import json
import mimetypes
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from devops_cli.ai.personas import (
    ANALYZE_PSEUDOCODE_SYSTEM_PROMPT,
    ANALYZE_PSEUDOCODE_TASK_PROMPT,
)
from devops_cli.config.constants import (
    CONST_DATA_DIR,
    CONST_MAX_FILE_SIZE_BYTES,
)
from devops_cli.core.cli import new_typer
from devops_cli.core.repo import find_repo_root, list_repo_files
from devops_cli.dry_run import is_dry_run
from devops_cli.lang import MESSAGES
from devops_cli.models.ai import AnalysisMetadata, FileAnalysisMeta, ProjectAnalysisMeta

app = new_typer(
    help=MESSAGES.analyze.app_help,
    no_args_is_help=True,
)
console = Console()

_MANIFEST_LANG_MAP: dict[str, str] = {
    "dockerfile": "dockerfile",
    "containerfile": "dockerfile",
    "makefile": "makefile",
    "gnumakefile": "makefile",
    "jenkinsfile": "jenkinsfile",
    "vagrantfile": "ruby",
    "rakefile": "ruby",
    "gemfile": "ruby",
    "procfile": "yaml",
    "cmakelists.txt": "cmake",
    ".gitignore": "gitignore",
    ".dockerignore": "dockerignore",
    ".env": "env",
    ".editorconfig": "ini",
}

_EXT_LANG_FALLBACK: dict[str, str] = {
    ".py": "python",
    ".pyw": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    ".jsx": "javascript",
    ".tsx": "typescript",
    ".html": "html",
    ".css": "css",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".ini": "ini",
    ".cfg": "ini",
    ".conf": "ini",
    ".xml": "xml",
    ".sql": "sql",
    ".proto": "protobuf",
    ".tf": "hcl",
    ".go": "go",
    ".rs": "rust",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".java": "java",
    ".kt": "kotlin",
    ".swift": "swift",
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
    ".md": "markdown",
}


def sanitize_reference(raw_ref: str, repo_root: Path | None = None) -> str:
    """Sanitize and normalize a reference into a safe filename string."""
    cleaned = raw_ref.strip()
    if cleaned in ("", ".", "./"):
        cleaned = repo_root.name if repo_root else "root"

    cleaned = cleaned.replace("/", "-").replace("\\", "-")
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "-", cleaned)
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    return cleaned or "root"


def detect_language(filepath: Path | str, content: str | None = None) -> str:
    """Detect file language using standard library mimetypes, shebangs, and manifest maps."""
    path_obj = Path(filepath)
    filename = path_obj.name.lower()
    ext = path_obj.suffix.lower()

    if filename in _MANIFEST_LANG_MAP:
        return _MANIFEST_LANG_MAP[filename]

    if filename.startswith("dockerfile."):
        return "dockerfile"

    if content:
        lines = content.splitlines()
        if lines and lines[0].startswith("#!"):
            sb = lines[0].lower()
            if "python" in sb:
                return "python"
            if any(sh in sb for sh in ("bash", "zsh", "sh")):
                return "shell"
            if any(js in sb for js in ("node", "deno", "bun")):
                return "javascript"

    mime_type, _ = mimetypes.guess_type(str(filepath))
    if mime_type:
        _, sub = mime_type.split("/", 1)
        sub_clean = sub.removeprefix("x-").removeprefix("vnd.").split(".")[0].split("+")[0]
        if sub_clean in (
            "python",
            "javascript",
            "typescript",
            "json",
            "yaml",
            "html",
            "css",
            "markdown",
            "shell",
            "c",
            "cpp",
            "go",
            "rust",
            "java",
            "sql",
            "xml",
            "toml",
            "ini",
        ):
            return sub_clean

    return _EXT_LANG_FALLBACK.get(ext, "plaintext")


def _analyze_python_ast(content: str) -> tuple[str | None, list[str], list[str]]:
    """Extract docstring, symbols, and imports using Python stdlib `ast`."""
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return None, [], []

    docstring = ast.get_docstring(tree)
    first_doc_sentence = docstring.strip().split("\n")[0].rstrip(".") if docstring else None

    symbols: list[str] = []
    for stmt in tree.body:
        if isinstance(stmt, ast.ClassDef):
            if stmt.name not in ("BaseModel", "ConfigDict", "Exception", "Any"):
                symbols.append(stmt.name)
        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not stmt.name.startswith("__"):
                symbols.append(stmt.name)
        elif isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    symbols.append(target.id)
        elif isinstance(stmt, ast.AnnAssign):
            if isinstance(stmt.target, ast.Name) and stmt.target.id.isupper():
                symbols.append(stmt.target.id)

    imports: list[str] = []
    std_modules = {
        "sys",
        "os",
        "re",
        "json",
        "typing",
        "pathlib",
        "datetime",
        "functools",
        "collections",
        "subprocess",
        "ast",
        "mimetypes",
        "fnmatch",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod_name = alias.name
                root_pkg = mod_name.split(".")[0]
                if root_pkg not in std_modules and mod_name not in imports:
                    imports.append(mod_name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mod_name = node.module
            root_pkg = mod_name.split(".")[0]
            if root_pkg not in std_modules and mod_name not in imports:
                imports.append(mod_name)

    return first_doc_sentence, symbols[:15], imports[:12]


def _extract_file_symbols(content: str, lang: str) -> list[str]:
    """Extract code symbols using stdlib AST for Python or standard regex fallback."""
    if lang == "python":
        _, ast_syms, _ = _analyze_python_ast(content)
        if ast_syms:
            return ast_syms

    symbols: list[str] = []
    for m in re.finditer(r"^\s*class\s+([A-Za-z0-9_]+)", content, re.MULTILINE):
        sym = m.group(1)
        if sym not in ("BaseModel", "ConfigDict", "Exception", "Any") and sym not in symbols:
            symbols.append(sym)
    for m in re.finditer(r"^\s*def\s+([A-Za-z0-9_]+)", content, re.MULTILINE):
        sym = m.group(1)
        if not sym.startswith("__") and sym not in symbols:
            symbols.append(sym)
    for m in re.finditer(r"\b(CONST_[A-Z0-9_]+|DEFAULT_[A-Z0-9_]+|OPTION_[A-Z0-9_]+)\b", content):
        sym = m.group(1)
        if sym not in symbols:
            symbols.append(sym)
    return symbols[:15]


def _extract_file_dependencies(content: str, lang: str) -> list[str]:
    """Extract package dependencies with submodules using AST or import scanners."""
    if lang == "python":
        _, _, imports = _analyze_python_ast(content)
        if imports:
            return imports

    if lang not in ("javascript", "typescript", "go", "rust", "java", "csharp"):
        return []

    deps: list[str] = []
    for line in content.splitlines():
        line_str = line.strip()
        if not line_str or line_str.startswith(("#", "//")):
            continue
        if line_str.startswith(("import ", "from ", "require(")):
            parts = line_str.split()
            if len(parts) >= 2:
                raw_pkg = parts[1].strip("'\"`;,")
                if raw_pkg and raw_pkg not in deps and not raw_pkg.startswith("."):
                    deps.append(raw_pkg)
    return deps[:12]


def _extract_file_purpose(rel_path: str, content: str, lang: str, symbols: list[str]) -> str:
    """Infer an accurate, human-meaningful primary purpose description for a file."""
    filename = Path(rel_path).name.lower()
    stem = Path(rel_path).stem

    # 1. Standard configuration & workspace metadata files
    if filename == "pyproject.toml":
        return "Python package configuration, dependencies, and build settings"
    if filename == ".gitignore":
        return "Git repository version control exclusion rules"
    if filename == ".editorconfig":
        return "Editor formatting rules and file indentation settings"
    if filename in ("dockerfile", "containerfile"):
        return "Docker container image build instructions"
    if filename == "makefile":
        return "Build target rules and development automation commands"
    if filename == ".python-version":
        return "Pin local Python runtime version"

    # 2. Python docstrings & Markdown titles
    if lang == "python" and content:
        doc_sentence, _, _ = _analyze_python_ast(content)
        if doc_sentence and len(doc_sentence) <= 140:
            return doc_sentence

    if lang == "markdown" and content:
        for line in content.splitlines():
            line_str = line.strip()
            if line_str.startswith("# "):
                title_text = line_str.removeprefix("# ").strip()
                if title_text:
                    return f"Documentation guide: {title_text}"

    # 3. Top-of-file header comments
    if content:
        for line in content.splitlines()[:12]:
            line_str = line.strip()
            if line_str.startswith(("#", "//", "/*", "<!--")) and not line_str.startswith(
                ("#!", "/*eslint")
            ):
                comment_text = (
                    re.sub(r"^(?:#|//|/\*|<!--|\*)\s*", "", line_str).rstrip("-->*/").strip()
                )
                if (
                    comment_text
                    and not comment_text.startswith(("─", "═", "-", "=", "*", "!"))
                    and len(set(comment_text)) > 2
                    and len(comment_text) <= 140
                ):
                    return comment_text

    # 4. JSON / YAML structural schema inspection
    if lang in ("json", "yaml", "toml") and content:
        try:
            if lang == "json":
                data = json.loads(content)
                if isinstance(data, dict) and data:
                    keys = [str(k) for k in list(data.keys())[:5]]
                    return f"Configuration asset with top-level keys: {', '.join(keys)}"
        except Exception:
            pass

    # 5. Shell script command inspection
    if lang in ("shell", "bash") and content:
        cmds: list[str] = []
        for line in content.splitlines():
            line_str = line.strip()
            if line_str and not line_str.startswith("#"):
                parts = line_str.split()
                if (
                    parts
                    and "=" not in parts[0]
                    and parts[0]
                    not in (
                        "if",
                        "then",
                        "else",
                        "fi",
                        "for",
                        "do",
                        "done",
                        "echo",
                        "export",
                        "set",
                        "local",
                    )
                ):
                    if parts[0] not in cmds:
                        cmds.append(parts[0])
                    if len(cmds) >= 4:
                        break
        if cmds:
            return f"Automation script executing commands: {', '.join(cmds)}"

    # 6. Symbol-based module purpose
    if symbols:
        main_syms = [s for s in symbols if not s.startswith("test_")][:3]
        if main_syms:
            return f"Defines {', '.join(main_syms)} logic for {stem}"

    # 7. Path heuristic
    lower_path = rel_path.lower()
    if "test" in lower_path:
        return f"Unit test suite for {stem}"

    return f"Source asset for {filename} ({lang})"


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

        proc = run_subprocess(
            ["git", "log", "-1", "--format=%cd", "--date=iso-strict", "--", rel_path],
            cwd=repo_root,
        )
        proc_out = str(proc.stdout).strip()
        if proc.returncode == 0 and proc_out:
            return proc_out
        file_abs = repo_root / rel_path
        if file_abs.exists():
            return datetime.fromtimestamp(file_abs.stat().st_mtime, UTC).isoformat()
    return datetime.now(UTC).isoformat()


def _is_import_or_docstring_line(line_str: str) -> bool:
    """Detect import statements or raw docstrings to exclude from pseudocode."""
    s = line_str.strip()
    if not s:
        return True
    if s.startswith(('"""', "'''", 'r"""', "r'''", 'f"""', "f'''")):
        return True
    low_s = s.lower()
    if (
        low_s.startswith(("import ", "from ", "package "))
        or "import " in low_s
        or "require(" in low_s
    ):
        return True
    return False


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

    # 1. Python source code outline via AST
    if lang == "python" and content.strip():
        py_outline = _extract_python_pseudocode_outline(content)
        if py_outline:
            return py_outline

    # 2. JSON / YAML / TOML configuration files (direct key: val without canned prose)
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

    # 3. Shell / bash scripts (actual command lines)
    if lang in ("shell", "bash") and content.strip():
        actual_cmds: list[str] = []
        for line in content.splitlines():
            line_str = line.strip()
            if line_str and not line_str.startswith("#"):
                actual_cmds.append(line_str[:80])
                if len(actual_cmds) >= 8:
                    break
        if actual_cmds:
            return actual_cmds

    # 4. Markdown / Documentation (header lines without "Section:" prefix)
    if lang == "markdown" and content.strip():
        headers = [
            line.strip().lstrip("#").strip()
            for line in content.splitlines()
            if line.strip().startswith("#")
        ][:8]
        if headers:
            return [h for h in headers if h]

    # 5. Generic code files with symbols
    if symbols:
        main_syms = [s for s in symbols if not s.startswith("test_")][:8]
        if not main_syms:
            main_syms = symbols[:8]
        if main_syms:
            return [f"{sym}(...)" for sym in main_syms]

    # 6. Generic configuration or text files (.editorconfig, .gitignore, etc.)
    non_comment_lines: list[str] = []
    for line in content.splitlines():
        line_str = line.strip()
        if (
            line_str
            and not line_str.startswith(("#", "//", ";", "<!--"))
            and not _is_import_or_docstring_line(line_str)
        ):
            non_comment_lines.append(line_str[:80])
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


def save_analysis_metadata(
    target_type: Literal["branch", "pr", "path"],
    target_reference: str,
    title: str,
    files: list[FileAnalysisMeta],
    repo_root: Path,
    enhanced: bool = True,
) -> Path:
    """Save or update analysis metadata file under .data/analysis/."""
    sanitized_ref = sanitize_reference(target_reference, repo_root)
    analysis_dir = repo_root / CONST_DATA_DIR / "analysis"
    if not is_dry_run():
        analysis_dir.mkdir(parents=True, exist_ok=True)
    out_file = analysis_dir / f"{target_type}-{sanitized_ref}-metadata.json"

    total_files = len(files)
    total_lines = sum(f.line_count for f in files)
    total_chars = sum(f.char_count for f in files)
    languages = sorted(list({f.language for f in files}))

    # Aggregate project key symbols & dependencies prioritizing core source modules
    all_symbols: list[str] = []
    core_files = [
        f for f in files if not f.path.lower().startswith("test") and "test_" not in f.path.lower()
    ]
    other_files = [f for f in files if f not in core_files]

    for f in core_files + other_files:
        for s in f.key_symbols:
            if (
                s not in all_symbols
                and not s.startswith(("test_", "dummy_", "mock_", "tmp_"))
                and s not in ("BaseModel", "ConfigDict", "Exception", "Any", "SampleSchema")
            ):
                all_symbols.append(s)

    all_deps: list[str] = []
    for f in files:
        for d in f.dependencies:
            if d not in all_deps:
                all_deps.append(d)

    project_purpose = (
        f"Analysis session for {target_type} '{target_reference}' covering {total_files} file(s)."
    )

    proj_meta = ProjectAnalysisMeta(
        title=title,
        target_type=target_type,
        target_reference=target_reference,
        timestamp=datetime.now(UTC).isoformat(),
        total_files=total_files,
        total_lines=total_lines,
        total_chars=total_chars,
        languages=languages,
        primary_purpose=project_purpose,
        key_symbols=all_symbols[:50],
        dependencies=all_deps[:15],
        enhanced=enhanced,
        last_analyzed=datetime.now(UTC).isoformat() if enhanced else None,
    )

    payload = AnalysisMetadata(project=proj_meta, files=files)

    if is_dry_run():
        rprint(MESSAGES.analyze.would_save_metadata.format(path=out_file))
        rprint("[yellow][dry-run][/yellow] AnalysisMetadata Pydantic model response:")
        console.print_json(payload.model_dump_json(indent=2))
    else:
        out_file.write_text(json.dumps(payload.model_dump(mode="json"), indent=2), encoding="utf-8")
        rprint(MESSAGES.analyze.saved_metadata.format(path=out_file))

    return out_file


def _render_analysis_summary(payload: AnalysisMetadata, out_path: Path) -> None:
    """Render a Rich summary table of the analysis metadata."""
    proj = payload.project
    console.print(MESSAGES.analyze.analysis_complete.format(title=proj.title))
    table = Table(show_header=False, box=None)
    table.add_row(MESSAGES.analyze.lbl_target, f"{proj.target_type} ({proj.target_reference})")
    table.add_row(MESSAGES.analyze.lbl_total_files, str(proj.total_files))
    table.add_row(MESSAGES.analyze.lbl_total_lines, f"{proj.total_lines:,}")
    table.add_row(MESSAGES.analyze.lbl_languages, ", ".join(proj.languages))
    if proj.enhanced:
        table.add_row(
            MESSAGES.analyze.lbl_enhanced,
            MESSAGES.analyze.enhanced_enabled,
        )
        table.add_row("Confidence Score:", f"{proj.confidence_score:.2f}")
    table.add_row(MESSAGES.analyze.lbl_saved_to, f"[link=file://{out_path}]{out_path}[/link]")
    console.print(table)


# ── Subcommands ───────────────────────────────────────────────────────────────


@app.command(name="path")
def analyze_path(
    target: Annotated[Path, typer.Argument(help="File or directory path to analyze")] = Path("."),
    pattern: Annotated[
        str,
        typer.Option("--pattern", "-g", help="Glob pattern for files (default: all files)"),
    ] = "*",
    enhanced: Annotated[
        bool,
        typer.Option(
            "--enhanced/--no-enhanced",
            "-e",
            help="Generate AI-enhanced metadata (pseudocode, complexity, last_updated)",
        ),
    ] = True,
    update_all: Annotated[
        bool,
        typer.Option(
            "--update-all",
            "-u",
            help="Regenerate all enhanced metadata fields regardless of last_* timestamps",
        ),
    ] = False,
) -> None:
    """Analyze a local directory path or single file and save metadata to .data/analysis/."""
    repo = find_repo_root(target)
    target_abs = target.resolve() if target.is_absolute() else (repo / target).resolve()

    if not target_abs.exists():
        rprint(f"[red]{MESSAGES.analyze.path_not_exists.format(path=target)}[/red]")
        raise typer.Exit(1)

    collected_paths = list_repo_files(target_abs)
    if pattern and pattern != "*":
        collected_paths = [p for p in collected_paths if fnmatch.fnmatch(p.name, pattern)]

    ai_client = None
    if enhanced and not is_dry_run():
        try:
            from devops_cli.ai.client import LLMClient
            from devops_cli.config.settings import get_ai_api_key, load_settings

            settings = load_settings()
            ai_client = LLMClient(settings.ai, api_key=get_ai_api_key(settings))
        except Exception:
            ai_client = None

    ref_str = str(target.relative_to(repo)) if target_abs != repo else repo.name
    sanitized_ref = sanitize_reference(ref_str, repo)
    existing_file_metas: dict[str, FileAnalysisMeta] = {}
    out_file_path = repo / CONST_DATA_DIR / "analysis" / f"path-{sanitized_ref}-metadata.json"

    if enhanced and not update_all and out_file_path.exists():
        try:
            existing_data = json.loads(out_file_path.read_text(encoding="utf-8"))
            existing_payload = AnalysisMetadata.model_validate(existing_data)
            existing_file_metas = {f.path: f for f in existing_payload.files}
        except Exception:
            existing_file_metas = {}

    file_metas: list[FileAnalysisMeta] = []
    for p in collected_paths:
        if p.stat().st_size > CONST_MAX_FILE_SIZE_BYTES:
            continue
        try:
            rel_str = str(p.relative_to(repo)) if p.is_relative_to(repo) else str(p)
            file_mtime = datetime.fromtimestamp(p.stat().st_mtime, UTC)

            if enhanced and rel_str in existing_file_metas:
                old_meta = existing_file_metas[rel_str]
                if old_meta.last_analyzed and old_meta.pseudocode:
                    try:
                        analyzed_dt = datetime.fromisoformat(old_meta.last_analyzed)
                        if file_mtime <= analyzed_dt:
                            reused_meta = old_meta.model_copy(
                                update={"last_analyzed": datetime.now(UTC).isoformat()}
                            )
                            file_metas.append(reused_meta)
                            continue
                    except Exception:
                        pass

            content = p.read_text(encoding="utf-8", errors="replace")
            meta = analyze_single_file(
                rel_str,
                content,
                p.stat().st_size,
                enhanced=enhanced,
                repo_root=repo,
                ai_client=ai_client,
            )
            file_metas.append(meta)
        except Exception:
            continue

    title = f"{repo.name} path analysis: {ref_str}"
    out_file = save_analysis_metadata("path", ref_str, title, file_metas, repo, enhanced=enhanced)

    if not is_dry_run():
        payload_data = json.loads(out_file.read_text(encoding="utf-8"))
        _render_analysis_summary(AnalysisMetadata.model_validate(payload_data), out_file)


@app.command(name="branch")
def analyze_branch(
    branch: Annotated[
        str | None, typer.Argument(help="Branch to analyze (default: active branch)")
    ] = None,
    base: Annotated[str, typer.Option("--base", "-b", help="Base branch for diff")] = "main",
    enhanced: Annotated[
        bool,
        typer.Option(
            "--enhanced/--no-enhanced",
            "-e",
            help="Generate AI-enhanced metadata (pseudocode, complexity, last_updated)",
        ),
    ] = True,
    update_all: Annotated[
        bool,
        typer.Option(
            "--update-all",
            "-u",
            help="Regenerate all enhanced metadata fields regardless of last_* timestamps",
        ),
    ] = False,
) -> None:
    """Analyze a git branch diff against base and save metadata to .data/analysis/."""
    from devops_cli.core.process import run_subprocess
    from devops_cli.git.operations import list_branches

    repo = find_repo_root()
    target_branch = branch or list_branches(repo).current
    if not target_branch:
        rprint(f"[red]{MESSAGES.analyze.git_branch_failed}[/red]")
        raise typer.Exit(1)

    ai_client = None
    if enhanced and not is_dry_run():
        try:
            from devops_cli.ai.client import LLMClient
            from devops_cli.config.settings import get_ai_api_key, load_settings

            settings = load_settings()
            ai_client = LLMClient(settings.ai, api_key=get_ai_api_key(settings))
        except Exception:
            ai_client = None

    sanitized_ref = sanitize_reference(target_branch, repo)
    existing_file_metas: dict[str, FileAnalysisMeta] = {}
    out_file_path = repo / CONST_DATA_DIR / "analysis" / f"branch-{sanitized_ref}-metadata.json"

    if enhanced and not update_all and out_file_path.exists():
        try:
            existing_data = json.loads(out_file_path.read_text(encoding="utf-8"))
            existing_payload = AnalysisMetadata.model_validate(existing_data)
            existing_file_metas = {f.path: f for f in existing_payload.files}
        except Exception:
            existing_file_metas = {}

    # Get changed files from git diff
    proc = run_subprocess(["git", "diff", "--name-status", f"{base}...{target_branch}"], cwd=repo)
    file_metas: list[FileAnalysisMeta] = []

    if proc.returncode == 0 and proc.stdout:
        for line in proc.stdout.splitlines():
            parts = line.strip().split(maxsplit=1)
            if len(parts) < 2:
                continue
            status, rel_path = parts[0], parts[1]
            change_type = (
                "added"
                if status.startswith("A")
                else ("deleted" if status.startswith("D") else "modified")
            )
            file_path = repo / rel_path

            if change_type == "deleted" or not file_path.exists():
                file_metas.append(
                    FileAnalysisMeta(
                        path=rel_path,
                        size_bytes=0,
                        line_count=0,
                        char_count=0,
                        language=detect_language(rel_path),
                        primary_purpose=f"Deleted file {Path(rel_path).name}",
                        key_symbols=[],
                        dependencies=[],
                        change_type="deleted",
                        pseudocode=None,
                        last_updated=None,
                        complexity_score=None,
                    )
                )
                continue

            try:
                file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime, UTC)
                if enhanced and rel_path in existing_file_metas:
                    old_meta = existing_file_metas[rel_path]
                    if old_meta.last_analyzed and old_meta.pseudocode:
                        try:
                            analyzed_dt = datetime.fromisoformat(old_meta.last_analyzed)
                            if file_mtime <= analyzed_dt:
                                reused_meta = old_meta.model_copy(
                                    update={"last_analyzed": datetime.now(UTC).isoformat()}
                                )
                                file_metas.append(reused_meta)
                                continue
                        except Exception:
                            pass

                content = file_path.read_text(encoding="utf-8", errors="replace")
                meta = analyze_single_file(
                    rel_path,
                    content,
                    file_path.stat().st_size,
                    change_type=change_type,
                    enhanced=enhanced,
                    repo_root=repo,
                    ai_client=ai_client,
                )
                file_metas.append(meta)
            except Exception:
                continue

    title = f"{repo.name} branch analysis: {target_branch} vs {base}"
    out_file = save_analysis_metadata(
        "branch", target_branch, title, file_metas, repo, enhanced=enhanced
    )

    if not is_dry_run():
        payload_data = json.loads(out_file.read_text(encoding="utf-8"))
        _render_analysis_summary(AnalysisMetadata.model_validate(payload_data), out_file)


@app.command(name="pr")
def analyze_pr(
    pr_number: Annotated[int, typer.Argument(help="GitHub PR number to analyze")],
    enhanced: Annotated[
        bool,
        typer.Option(
            "--enhanced/--no-enhanced",
            "-e",
            help="Generate AI-enhanced metadata (pseudocode, complexity, last_updated)",
        ),
    ] = True,
    update_all: Annotated[
        bool,
        typer.Option(
            "--update-all",
            "-u",
            help="Regenerate all enhanced metadata fields regardless of last_* timestamps",
        ),
    ] = False,
) -> None:
    """Analyze a GitHub Pull Request and save metadata to .data/analysis/."""
    from devops_cli.config.settings import get_github_token, load_settings
    from devops_cli.github.client import GitHubClient

    repo = find_repo_root()
    settings = load_settings()
    token = get_github_token(settings)
    if not token:
        rprint(f"[red]{MESSAGES.analyze.github_token_required}[/red]")
        raise typer.Exit(1)

    ai_client = None
    if enhanced and not is_dry_run():
        try:
            from devops_cli.ai.client import LLMClient
            from devops_cli.config.settings import get_ai_api_key, load_settings

            settings = load_settings()
            ai_client = LLMClient(settings.ai, api_key=get_ai_api_key(settings))
        except Exception:
            ai_client = None

    from devops_cli.core.repo import get_repo_origin_name

    repo_name = get_repo_origin_name(repo)
    if not repo_name:
        rprint(f"[red]{MESSAGES.analyze.github_origin_failed}[/red]")
        raise typer.Exit(1)

    gh_client = GitHubClient(token=token)
    pull = gh_client.get_pull(repo_name, pr_number)
    file_metas: list[FileAnalysisMeta] = []

    for f_file in pull.get_files():
        path = f_file.filename
        if not path:
            continue
        status = str(f_file.status)
        file_path = repo / path
        if file_path.exists() and status != "removed":
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                meta = analyze_single_file(
                    path,
                    content,
                    file_path.stat().st_size,
                    change_type=status,
                    enhanced=enhanced,
                    repo_root=repo,
                    ai_client=ai_client,
                )
                file_metas.append(meta)
                continue
            except Exception:
                pass

        file_metas.append(
            FileAnalysisMeta(
                path=path,
                size_bytes=int(f_file.changes),
                line_count=int(f_file.additions),
                char_count=int(f_file.changes),
                language=detect_language(path),
                primary_purpose=f"PR file {Path(path).name}",
                key_symbols=[],
                dependencies=[],
                change_type=status,
                pseudocode=None,
                last_updated=None,
                complexity_score=None,
            )
        )

    title = f"{repo.name} PR #{pr_number} analysis: {pull.title}"
    ref_str = str(pr_number)
    out_file = save_analysis_metadata("pr", ref_str, title, file_metas, repo, enhanced=enhanced)

    if not is_dry_run():
        payload_data = json.loads(out_file.read_text(encoding="utf-8"))
        _render_analysis_summary(AnalysisMetadata.model_validate(payload_data), out_file)
