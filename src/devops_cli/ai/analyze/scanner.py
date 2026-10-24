"""AST import parsing, language detection, and dependency scanning logic."""

from __future__ import annotations

import ast
import mimetypes
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from devops_cli.ai.ast.engine import _header_language
from devops_cli.config.defaults import (
    DEFAULT_CURRENT_PATH,
    DEFAULT_MAX_AST_FILE_SIZE_BYTES,
)

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
    ".cc": "cpp",
    ".cpp": "cpp",
    ".cxx": "cpp",
    ".c++": "cpp",
    ".hh": "cpp",
    ".hpp": "cpp",
    ".hxx": "cpp",
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


_CPP_EXTENSIONS = frozenset({".cc", ".cpp", ".cxx", ".c++", ".hh", ".hpp", ".hxx"})


def _has_chart_manifest(directory: Path) -> bool:
    try:
        return (directory / "Chart.yaml").is_file() or (directory / "chart.yaml").is_file()
    except OSError:
        return False


def _is_helm_template(path_obj: Path) -> bool:
    """True when path_obj is a .tpl file inside a Helm chart (beside Chart.yaml)."""
    if path_obj.suffix.lower() != ".tpl":
        return False
    try:
        current = path_obj.resolve().parent
        for _ in range(5):
            if _has_chart_manifest(current):
                return True
            if current.parent == current:
                break
            current = current.parent
    except OSError:
        return False
    return False


def _detect_header_language(path_obj: Path, content: str | None) -> str:
    """Detect whether a .h header is C or C++."""
    if content is not None:
        return _header_language(content)
    if path_obj.is_file():
        try:
            return _header_language(path_obj.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            pass
    return "c"


def _detect_shebang_language(content: str) -> str | None:
    """Detect script language from shebang line."""
    first_line = content.splitlines()[:1]
    if not first_line or not first_line[0].startswith("#!"):
        return None
    sb = first_line[0].lower()
    if "python" in sb:
        return "python"
    if any(sh in sb for sh in ("bash", "zsh", "sh")):
        return "shell"
    if any(js in sb for js in ("node", "deno", "bun")):
        return "javascript"
    return None


def _detect_mime_language(filepath: str) -> str | None:
    """Detect file language from standard library mimetypes."""
    mime_type, _ = mimetypes.guess_type(filepath)
    if not mime_type or "/" not in mime_type:
        return None
    _, sub = mime_type.split("/", 1)
    if "c++" in sub:
        return "cpp"
    sub_clean = sub.removeprefix("x-").removeprefix("vnd.").split(".")[0].split("+")[0]
    if sub_clean in _VALID_MIME_SUBTYPES:
        return sub_clean
    return None


def detect_language(filepath: Path | str, content: str | None = None) -> str:
    """Detect file language using standard library mimetypes, shebangs, and manifest maps."""
    path_obj = Path(filepath)
    filename = path_obj.name.lower()
    ext = path_obj.suffix.lower()

    if filename in _MANIFEST_LANG_MAP:
        return _MANIFEST_LANG_MAP[filename]

    if filename.startswith("dockerfile."):
        return "dockerfile"

    if ext in _CPP_EXTENSIONS:
        return "cpp"

    if ext == ".h":
        return _detect_header_language(path_obj, content)

    if ext == ".tpl" and _is_helm_template(path_obj):
        return "helm"

    if content:
        shebang_lang = _detect_shebang_language(content)
        if shebang_lang:
            return shebang_lang

    mime_lang = _detect_mime_language(str(filepath))
    if mime_lang:
        return mime_lang

    return _EXT_LANG_FALLBACK.get(ext, "plaintext")


CODE_LANGUAGES: frozenset[str] = frozenset(
    {
        "bash",
        "c",
        "cpp",
        "csharp",
        "go",
        "java",
        "javascript",
        "kotlin",
        "lua",
        "php",
        "powershell",
        "python",
        "ruby",
        "rust",
        "scala",
        "shell",
        "swift",
        "tsx",
        "typescript",
    }
)


def syntax_from_language(lang: str | None) -> Literal["code", "data"]:
    """Return whether a detected language has 'code' or 'data' syntax."""
    if not lang:
        return "data"
    return "code" if lang.strip().lower() in CODE_LANGUAGES else "data"


def detect_syntax(filepath: Path | str, content: str | None = None) -> Literal["code", "data"]:
    """Detect whether a file path has 'code' or 'data' syntax based on its language."""
    return syntax_from_language(detect_language(filepath, content))


def _extract_ast_symbols(body: list[ast.stmt]) -> list[str]:
    """Extract class, function, and constant symbol names from Python AST body."""
    symbols: list[str] = []
    for stmt in body:
        match stmt:
            case ast.ClassDef(name=name) if name not in (
                "BaseModel",
                "ConfigDict",
                "Exception",
                "Any",
            ):
                symbols.append(name)
            case ast.FunctionDef(name=name) | ast.AsyncFunctionDef(name=name) if (
                not name.startswith("__")
            ):
                symbols.append(name)
            case ast.Assign(targets=targets):
                symbols.extend(
                    target.id
                    for target in targets
                    if isinstance(target, ast.Name) and target.id.isupper()
                )
            case ast.AnnAssign(target=ast.Name(id=name)) if name.isupper():
                symbols.append(name)
    return symbols


def _extract_ast_imports(tree: ast.AST, std_modules: frozenset[str]) -> list[str]:
    """Extract non-stdlib imports from AST tree."""
    imports: list[str] = []
    for node in ast.walk(tree):
        candidates = (
            [a.name for a in node.names]
            if isinstance(node, ast.Import)
            else ([node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
        )
        for name in candidates:
            root = name.split(".")[0]
            if root not in std_modules and name not in imports:
                imports.append(name)
    return imports


def _analyze_python_ast(content: str) -> tuple[str | None, list[str], list[str]]:
    """Extract docstring, symbols, and imports using Python stdlib `ast`."""
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return None, [], []

    docstring = ast.get_docstring(tree)
    first_doc = docstring.strip().split("\n")[0].rstrip(".") if docstring else None

    std_modules = sys.stdlib_module_names
    symbols = _extract_ast_symbols(tree.body)
    imports = _extract_ast_imports(tree, std_modules)

    return first_doc, symbols[:15], imports[:12]


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


def _extract_js_dep(line_str: str, pat: re.Pattern[str]) -> list[str]:
    """Extract JavaScript/TypeScript package identifiers from a code line."""
    res: list[str] = []
    for match in pat.finditer(line_str):
        raw = match.group(1)
        pkg = raw.split("/")[0] if not raw.startswith("@") else "/".join(raw.split("/")[:2])
        if pkg and not pkg.startswith("."):
            res.append(pkg)
    return res


def _extract_line_deps(
    line_str: str,
    lang: str,
    js_pattern: re.Pattern[str],
    go_pattern: re.Pattern[str],
    rust_pattern: re.Pattern[str],
) -> list[str]:
    """Extract package dependencies from a single non-comment code line."""
    if lang in ("javascript", "typescript"):
        return _extract_js_dep(line_str, js_pattern)
    if lang == "go":
        return [m.group(1) for m in go_pattern.finditer(line_str) if m.group(1)]
    if lang == "rust":
        return [
            m.group(1)
            for m in rust_pattern.finditer(line_str)
            if m.group(1) and m.group(1) not in ("crate", "super", "self", "std")
        ]
    if line_str.startswith(("import ", "from ", "require(")):
        parts = line_str.split()
        if len(parts) >= 2:
            raw_pkg = parts[1].strip("'\"`;,")
            if raw_pkg and not raw_pkg.startswith("."):
                return [raw_pkg]
    return []


def _extract_file_dependencies(content: str, lang: str) -> list[str]:
    """Extract package dependencies with submodules using AST or import scanners."""
    if lang == "python":
        _, _, imports = _analyze_python_ast(content)
        if imports:
            return imports

    if lang not in ("javascript", "typescript", "go", "rust", "java", "csharp"):
        return []

    deps: list[str] = []
    js_pat = re.compile(r"""(?:from|import|require)\s*\(?['"]([^'"./][^'"]*)['"]\)?""")
    go_pat = re.compile(r"""import\s+['"]([^'"]+)['"]""")
    rust_pat = re.compile(r"""use\s+([a-zA-Z0-9_]+)::""")

    for line in content.splitlines():
        line_str = line.strip()
        if not line_str or line_str.startswith(("#", "//")):
            continue
        for dep in _extract_line_deps(line_str, lang, js_pat, go_pat, rust_pat):
            if dep not in deps:
                deps.append(dep)
    return deps[:12]


def _extract_file_purpose(rel_path: str, content: str, lang: str, symbols: list[str]) -> str:  # noqa: C901
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


def scan_directory(target_dir: Path = DEFAULT_CURRENT_PATH) -> list[FileAnalysisMeta]:
    """Scan directory and return basic FileAnalysisMeta for each file."""
    from devops_cli.ai.analyze.outlines import analyze_single_file
    from devops_cli.core.paths import validate_no_path_traversal
    from devops_cli.core.repo import find_repo_root, list_repo_files
    from devops_cli.exceptions import SecurityError

    validate_no_path_traversal(target_dir)
    repo = find_repo_root(target_dir)
    repo_resolved = repo.resolve()
    target_abs = target_dir.resolve() if target_dir.is_absolute() else (repo / target_dir).resolve()
    if not target_abs.is_relative_to(repo_resolved):
        raise SecurityError(f"Target directory {target_abs} escapes repository root {repo}")

    collected_paths = list_repo_files(target_abs)
    results: list[FileAnalysisMeta] = []
    for file_path in collected_paths:
        try:
            resolved_file = file_path.resolve()
            if file_path.is_symlink() or not resolved_file.is_relative_to(repo_resolved):
                continue
            rel_path = str(file_path.relative_to(repo))
        except ValueError, OSError, RuntimeError:
            continue
        content = ""
        size_bytes = 0
        if file_path.is_file():
            try:
                size_bytes = file_path.stat().st_size
                if size_bytes <= DEFAULT_MAX_AST_FILE_SIZE_BYTES:
                    content = file_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass
        fmeta = analyze_single_file(rel_path, content, size_bytes, repo_root=repo)
        results.append(fmeta)
    return results
