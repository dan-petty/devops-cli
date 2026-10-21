"""Relational edge extractors across symbol imports, markdown references, and git history."""

from __future__ import annotations

import ast
import logging
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from markdown_it import MarkdownIt

from devops_cli.ai.research.models import ForageEdge
from devops_cli.config.defaults import DEFAULT_AI_FORAGE_MAX_COMMITS

logger = logging.getLogger(__name__)


def _resolve_import_candidate(parts: tuple[str, ...], root: Path) -> Path | None:
    cand = root.joinpath(*parts)
    py_file = cand.with_suffix(".py")
    if py_file.is_file():
        return py_file
    pkg_init = cand / "__init__.py"
    if pkg_init.is_file():
        return pkg_init
    return None


def _resolve_absolute_import(module_name: str, repo_root: Path) -> Path | None:
    parts = tuple(module_name.split("."))
    candidate_roots = (repo_root, repo_root / "src")
    for root in candidate_roots:
        for i in range(len(parts), 0, -1):
            resolved = _resolve_import_candidate(parts[:i], root)
            if resolved is not None:
                return resolved
    return None


def _resolve_relative_import(module_name: str, level: int, current_file: Path) -> Path | None:
    base = current_file.parent
    for _ in range(level - 1):
        base = base.parent
    parts = tuple(module_name.split(".")) if module_name else ()
    if not parts:
        pkg_init = base / "__init__.py"
        return pkg_init if pkg_init.is_file() else None
    return _resolve_import_candidate(parts, base)


def _resolve_import_path(
    module_name: str, level: int, current_file: Path, repo_root: Path
) -> str | None:
    target = (
        _resolve_relative_import(module_name, level, current_file)
        if level > 0
        else _resolve_absolute_import(module_name, repo_root)
    )
    if target and target.is_file() and target != current_file and target.is_relative_to(repo_root):
        return target.relative_to(repo_root).as_posix()
    return None


def _edges_from_import(
    node: ast.Import,
    file_path: Path,
    repo_root: Path,
    rel_src: str,
    seen: set[str],
) -> list[ForageEdge]:
    edges: list[ForageEdge] = []
    for alias in node.names:
        tgt = _resolve_import_path(alias.name, 0, file_path, repo_root)
        if tgt and tgt not in seen:
            seen.add(tgt)
            edges.append(
                ForageEdge(
                    source=rel_src,
                    target=tgt,
                    edge_type="import",
                    detail=alias.name,
                    weight=1.0,
                )
            )
    return edges


def _edge_for_submodule(
    mod: str,
    alias_name: str,
    level: int,
    file_path: Path,
    repo_root: Path,
    rel_src: str,
    seen: set[str],
) -> ForageEdge | None:
    sub_mod = f"{mod}.{alias_name}"
    sub_tgt = _resolve_import_path(sub_mod, level, file_path, repo_root)
    if sub_tgt and sub_tgt not in seen:
        seen.add(sub_tgt)
        return ForageEdge(
            source=rel_src,
            target=sub_tgt,
            edge_type="import",
            detail=sub_mod,
            weight=1.0,
        )
    return None


def _edges_from_import_from(
    node: ast.ImportFrom,
    file_path: Path,
    repo_root: Path,
    rel_src: str,
    seen: set[str],
) -> list[ForageEdge]:
    edges: list[ForageEdge] = []
    mod = node.module or ""
    tgt = _resolve_import_path(mod, node.level, file_path, repo_root)
    if tgt and tgt not in seen:
        seen.add(tgt)
        edges.append(
            ForageEdge(
                source=rel_src,
                target=tgt,
                edge_type="import",
                detail=mod or ".",
                weight=1.0,
            )
        )
    if not mod:
        return edges
    for alias in node.names:
        edge = _edge_for_submodule(mod, alias.name, node.level, file_path, repo_root, rel_src, seen)
        if edge:
            edges.append(edge)
    return edges


def _collect_ast_import_edges(
    tree: ast.AST, file_path: Path, repo_root: Path, rel_src: str
) -> list[ForageEdge]:
    edges: list[ForageEdge] = []
    seen: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            edges.extend(_edges_from_import(node, file_path, repo_root, rel_src, seen))
        elif isinstance(node, ast.ImportFrom):
            edges.extend(_edges_from_import_from(node, file_path, repo_root, rel_src, seen))
    return edges


def extract_python_imports(file_path: Path, repo_root: Path) -> list[ForageEdge]:
    """Extract Python symbol import edges from a source file."""
    if file_path.suffix != ".py":
        return []
    try:
        source = file_path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(file_path))
    except OSError, SyntaxError:
        return []
    rel_src = file_path.relative_to(repo_root).as_posix()
    return _collect_ast_import_edges(tree, file_path, repo_root, rel_src)


def _clean_markdown_href(href: str) -> str | None:
    if not href:
        return None
    clean = href.strip()
    if clean.startswith("#") or urlsplit(clean).scheme in {"http", "https", "mailto", "ftp"}:
        return None
    clean = clean.split("#", 1)[0].split("?", 1)[0]
    return clean if clean else None


def _extract_href_from_token(token: Any) -> str | None:
    if token.type == "link_open" and token.attrs and "href" in token.attrs:
        return str(token.attrs["href"])
    return None


def _collect_markdown_hrefs(tokens: list[Any]) -> list[str]:
    hrefs: list[str] = []
    for token in tokens:
        h = _extract_href_from_token(token)
        if h:
            hrefs.append(h)
        for child in getattr(token, "children", None) or []:
            ch = _extract_href_from_token(child)
            if ch:
                hrefs.append(ch)
    return hrefs


def extract_markdown_links(file_path: Path, repo_root: Path) -> list[ForageEdge]:
    """Extract internal markdown cross-reference link edges."""
    if file_path.suffix.lower() not in {".md", ".markdown"}:
        return []
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    tokens = MarkdownIt().parse(content)
    hrefs = _collect_markdown_hrefs(tokens)
    rel_src = file_path.relative_to(repo_root).as_posix()
    edges: list[ForageEdge] = []
    seen: set[str] = set()

    for href in hrefs:
        cleaned = _clean_markdown_href(href)
        if not cleaned:
            continue
        try:
            target = (file_path.parent / cleaned).resolve()
            if target.is_file() and target.is_relative_to(repo_root):
                tgt_rel = target.relative_to(repo_root).as_posix()
                if tgt_rel != rel_src and tgt_rel not in seen:
                    seen.add(tgt_rel)
                    edges.append(
                        ForageEdge(
                            source=rel_src,
                            target=tgt_rel,
                            edge_type="markdown_link",
                            detail=href,
                            weight=1.0,
                        )
                    )
        except OSError, RuntimeError, ValueError:
            continue
    return edges


def extract_git_co_changes(
    file_path: Path,
    repo_root: Path,
    max_commits: int = DEFAULT_AI_FORAGE_MAX_COMMITS,
) -> list[ForageEdge]:
    """Extract co-change edges from git history using GitPython."""
    try:
        import git

        repo = git.Repo(repo_root)
        rel_path = file_path.relative_to(repo_root).as_posix()
        commits = list(repo.iter_commits(paths=rel_path, max_count=max_commits))
    except (git.exc.GitError, OSError, ValueError) as exc:
        logger.debug("Failed opening git repo at %s: %s", repo_root, exc)
        return []

    if not commits:
        return []

    counts: Counter[str] = Counter()
    for commit in commits:
        try:
            files_dict = commit.stats.files
        except (git.exc.GitError, OSError, ValueError) as exc:
            logger.debug("Failed reading commit stats for %s: %s", commit.hexsha, exc)
            files_dict = {}
        for changed in files_dict.keys():
            changed_str = str(changed)
            if changed_str != rel_path:
                counts[changed_str] += 1

    edges: list[ForageEdge] = []
    for other, count in counts.most_common():
        tgt_path = repo_root / other
        if tgt_path.is_file() and not tgt_path.is_symlink():
            weight = count / len(commits)
            edges.append(
                ForageEdge(
                    source=rel_path,
                    target=other,
                    edge_type="git_co_change",
                    detail=f"{count} co-commits",
                    weight=round(weight, 3),
                )
            )
    return edges
