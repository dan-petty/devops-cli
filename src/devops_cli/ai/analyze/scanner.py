"""AST import parsing, language detection, and dependency scanning logic."""

from __future__ import annotations

import ast
import mimetypes
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from devops_cli.models.ai import FileAnalysisMeta


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
    ".cs": "csharp",
    ".rb": "ruby",
    ".php": "php",
    ".scala": "scala",
    ".lua": "lua",
    ".fish": "shell",
    ".ps1": "powershell",
    ".rst": "rst",
    ".adoc": "asciidoc",
    ".asciidoc": "asciidoc",
    ".org": "org",
    ".txt": "text",
    ".md": "markdown",
    ".markdown": "markdown",
}


def sanitize_reference(raw_ref: str, repo_root: Path | None = None) -> str:
    """Sanitize and normalize a reference into a safe filename string with max length."""
    cleaned = raw_ref.strip()
    if cleaned in ("", ".", "./"):
        cleaned = repo_root.name if repo_root else "root"

    cleaned = cleaned.replace("/", "-").replace("\\", "-")
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "-", cleaned)
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    if len(cleaned) > 128:
        cleaned = cleaned[:128].rstrip("-")
    return cleaned or "root"


_VALID_MIME_SUBTYPES = {
    "python",
    "javascript",
    "typescript",
    "json",
    "yaml",
    "html",
    "css",
    "markdown",
    "xml",
    "sql",
    "shell",
    "c",
    "cpp",
    "go",
    "rust",
    "ruby",
    "protobuf",
}


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
        if sub_clean in _VALID_MIME_SUBTYPES:
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
        elif isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef):
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

    if content:
        for line in content.splitlines()[:5]:
            line_str = line.strip()
            if line_str.startswith(("# ", "// ", "/* ", '"""', "'''")):
                clean_comment = (
                    line_str.lstrip("#/ *'\"").rstrip("*'\".").strip().split(".")[0].strip()
                )
                if clean_comment and len(clean_comment) >= 10 and len(clean_comment) <= 120:
                    return clean_comment

    if symbols:
        main_syms = ", ".join(symbols[:3])
        return f"Implements core code logic around {main_syms}"

    clean_stem = stem.replace("_", " ").replace("-", " ").title()
    return f"Provides module implementation for {clean_stem}"


def scan_directory(target_dir: Path = Path(".")) -> list[FileAnalysisMeta]:
    """Scan directory and return basic FileAnalysisMeta for each file."""
    from devops_cli.ai.analyze.outlines import analyze_single_file
    from devops_cli.core.repo import find_repo_root, list_repo_files

    repo = find_repo_root(target_dir)
    target_abs = target_dir.resolve() if target_dir.is_absolute() else (repo / target_dir).resolve()
    collected_paths = list_repo_files(target_abs)
    results: list[FileAnalysisMeta] = []
    for file_path in collected_paths:
        try:
            rel_path = str(file_path.relative_to(repo))
        except ValueError:
            rel_path = file_path.name
        content = ""
        size_bytes = 0
        if file_path.exists():
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                size_bytes = file_path.stat().st_size
            except OSError:
                pass
        fmeta = analyze_single_file(rel_path, content, size_bytes, repo_root=repo)
        results.append(fmeta)
    return results
