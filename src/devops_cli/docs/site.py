"""Stage and build the docs site with Zensical, and check the built pages (#5152).

The site publishes `docs/` and the root documents of the repository at their repository paths, so
each relative link that works on github.com also works on the site. Zensical runs no MkDocs hooks,
so the stage changes each relative link to a repository file outside the site into a link to that
file on GitHub at the commit of the build. The stage also writes the build data (version, commit,
commit date and build time) into the staged config, where the footer template reads it.
"""

from __future__ import annotations

import posixpath
import shutil
import tomllib
from collections.abc import Iterator
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Final
from urllib.parse import quote, unquote, urlsplit

import yaml
from pydantic import BaseModel, ConfigDict

from devops_cli.config.constants import CONST_DOCS_SITE_CONFIG_FILE
from devops_cli.core.binaries import require_binary
from devops_cli.core.process import run_subprocess
from devops_cli.core.repo import resolve_store_path
from devops_cli.exceptions.tools import SubprocessError
from devops_cli.exceptions.validation import DocsSiteError
from devops_cli.lang import MESSAGES

# The stage, in the data directory (`.data/site-src/` by default). Zensical needs the pages and
# the built site under the folder of its config file, so the stage holds the staged config,
# `pages/` and `site/`.
_STAGE_STORE: Final = "site-src"
_STAGED_CONFIG: Final = "zensical.yml"
_STAGED_PAGES: Final = "pages"
_STAGED_SITE: Final = "site"
# The navigation of the awesome-nav plugin, at the root of the pages.
_NAV_FILE: Final = ".nav.yml"
_OVERRIDES_DIR: Final = "overrides"
_DOCS_DIR: Final = "docs"
# The root documents that the site publishes besides `docs/`.
SITE_ROOT_DOCUMENTS: Final = (
    "README.md",
    "ARCHITECTURE.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "RELEASE_CYCLE.md",
    "CONTEXT.md",
    "AGENTS.md",
    "CHANGELOG.md",
)
# The folders of `docs/` that the site does not publish: the agent records.
_UNPUBLISHED_DOCS: Final = frozenset({"agent"})
# A page of a folder: Zensical builds `index.md` and `README.md` as the page of their folder.
_FOLDER_PAGES: Final = frozenset({"index.md", "README.md"})
_PAGE_SUFFIX: Final = ".md"
# The meta tag of each built page that holds the commit of the build.
BUILD_COMMIT_META: Final = "devops-build-commit"
_BUILT_PAGE: Final = "index.html"
_NAV_LINK_CLASS: Final = "md-nav__link"
# The inline nodes of the block grammar of tree-sitter-markdown: a table cell has no inline child.
_INLINE_NODES: Final = frozenset({"inline", "pipe_table_cell"})
_DESTINATION_QUERY: Final = (
    "[(inline_link (link_destination) @link) (image (link_destination) @image)]"
)
_GIT_SHOW: Final = ("git", "show", "--no-patch", "--format=%H%n%h%n%cs", "HEAD")
_ZENSICAL: Final = "zensical"
_ZENSICAL_INSTALL_HINT: Final = "Run 'uv sync --group docs'."
# A build of about 110 pages takes about 10 s; the bound leaves the CI step time to report.
_BUILD_TIMEOUT_SECONDS: Final = 180.0
# The preview server runs until the user stops it; the bound is one working day.
_SERVE_TIMEOUT_SECONDS: Final = 8 * 3600.0


class BuildData(BaseModel):
    """The build data that each page of the site shows."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str
    commit: str
    short_commit: str
    commit_url: str
    commit_date: str
    built_at: str


class StagedSite(BaseModel):
    """The stage of one build: the staged config, the pages and the folder of the built site."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    config_file: Path
    pages_dir: Path
    site_dir: Path
    pages: int
    rewritten_links: int


class SiteDefects(BaseModel):
    """The built pages that no nav tab lists, and the built pages without the build commit."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    outside_nav: list[str]
    without_build_commit: list[str]


class SiteBuildReport(BaseModel):
    """The result of `devops docs site build`. A served site has no built pages to check."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    build: BuildData
    staged: StagedSite
    built_pages: int = 0
    defects: SiteDefects | None = None


def read_site_config(repo_root: Path) -> dict[str, Any]:
    """The `[project]` table of `zensical.toml`: the site settings of the repository."""
    path = repo_root / CONST_DOCS_SITE_CONFIG_FILE
    if not path.is_file():
        raise DocsSiteError(
            MESSAGES.docs.site_config_missing.format(path=path), details={"path": str(path)}
        )
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    project = data.get("project", data)
    if not project.get("repo_url"):
        raise DocsSiteError(
            MESSAGES.docs.site_setting_missing.format(setting="repo_url", path=path),
            field="repo_url",
        )
    return dict(project)


def read_build_data(repo_root: Path, *, built_at: datetime) -> BuildData:
    """The version of `pyproject.toml`, the commit of the checkout and its date, and `built_at`."""
    repo_url = str(read_site_config(repo_root)["repo_url"]).rstrip("/")
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    result = run_subprocess(list(_GIT_SHOW), cwd=repo_root, local_read=True, quiet=True)
    if result.returncode != 0:
        raise SubprocessError(
            MESSAGES.docs.site_commit_unread,
            command=list(_GIT_SHOW),
            exit_code=result.returncode,
            stderr=result.stderr,
        )
    commit, short_commit, commit_date = result.stdout.split()
    return BuildData(
        version=str(pyproject["project"]["version"]),
        commit=commit,
        short_commit=short_commit,
        commit_url=f"{repo_url}/commit/{commit}",
        commit_date=commit_date,
        built_at=built_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def stage_site(repo_root: Path, stage_dir: Path, build: BuildData) -> StagedSite:
    """Copy the site pages to `stage_dir` at their repository paths, change each link to a
    repository file outside the site into a GitHub link, and write the staged config."""
    missing = [name for name in SITE_ROOT_DOCUMENTS if not (repo_root / name).is_file()]
    if missing:
        raise DocsSiteError(
            MESSAGES.docs.site_documents_missing.format(names=", ".join(missing)),
            details={"missing": missing},
        )
    config = read_site_config(repo_root)
    pages_dir = stage_dir / _STAGED_PAGES
    site_dir = stage_dir / _STAGED_SITE
    for folder in (pages_dir, site_dir):
        if folder.exists():
            shutil.rmtree(folder)
    _copy_pages(repo_root, pages_dir)
    published = _published_paths(pages_dir)
    links = _GitHubLinks(str(config["repo_url"]).rstrip("/"), build.commit, repo_root, published)
    page_files = sorted(pages_dir.rglob(f"*{_PAGE_SUFFIX}"))
    finder = _LinkFinder()
    rewritten = sum(_rewrite_page(page, pages_dir, finder, links) for page in page_files)
    config_file = stage_dir / _STAGED_CONFIG
    config_file.write_text(
        yaml.safe_dump(_staged_config(config, repo_root, build), sort_keys=False),
        encoding="utf-8",
    )
    return StagedSite(
        config_file=config_file,
        pages_dir=pages_dir,
        site_dir=site_dir,
        pages=len(page_files),
        rewritten_links=rewritten,
    )


def built_pages(site_dir: Path) -> list[str]:
    """The URL path of each built page under `site_dir`: `""` for the home page, else `a/b/`."""
    return sorted(
        _page_key(page.parent.relative_to(site_dir).as_posix())
        for page in site_dir.rglob(_BUILT_PAGE)
    )


def check_built_site(site_dir: Path, build: BuildData) -> SiteDefects:
    """Find the built pages that the nav of the home page does not list, and the built pages
    whose `devops-build-commit` meta tag does not hold the commit of `build`."""
    nav = _BuiltPage.read(site_dir / _BUILT_PAGE).nav_pages
    outside_nav: list[str] = []
    without_build_commit: list[str] = []
    for page in built_pages(site_dir):
        if page not in nav:
            outside_nav.append(page)
        if (
            _BuiltPage.read(site_dir / page / _BUILT_PAGE, head_only=True).build_commit
            != build.commit
        ):
            without_build_commit.append(page)
    return SiteDefects(outside_nav=outside_nav, without_build_commit=without_build_commit)


def build_site(
    repo_root: Path, *, strict: bool, serve: bool, built_at: datetime
) -> SiteBuildReport:
    """Stage the site, build it (or build and serve it) with Zensical, and check the built pages.

    With `strict`, Zensical fails on a warning, such as a link to a missing page or anchor, and
    a built page that no nav tab lists or that lacks the build commit fails the build.
    """
    build = read_build_data(repo_root, built_at=built_at)
    staged = stage_site(repo_root, resolve_store_path(_STAGE_STORE, start_path=repo_root), build)
    require_binary(_ZENSICAL, install_hint=_ZENSICAL_INSTALL_HINT)
    action = "serve" if serve else "build"
    cmd = [_ZENSICAL, action, "--config-file", str(staged.config_file)]
    if strict and not serve:
        cmd.append("--strict")
    result = run_subprocess(
        cmd,
        cwd=staged.config_file.parent,
        capture_output=False,
        timeout=_SERVE_TIMEOUT_SECONDS if serve else _BUILD_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        raise SubprocessError(
            MESSAGES.docs.site_build_failed.format(code=result.returncode),
            command=cmd,
            exit_code=result.returncode,
        )
    if serve:
        return SiteBuildReport(build=build, staged=staged)
    defects = check_built_site(staged.site_dir, build)
    if strict and (defects.outside_nav or defects.without_build_commit):
        raise DocsSiteError(
            MESSAGES.docs.site_defects.format(
                outside_nav=", ".join(defects.outside_nav) or "-",
                without_build_commit=", ".join(defects.without_build_commit) or "-",
            ),
            details=defects.model_dump(),
        )
    return SiteBuildReport(
        build=build, staged=staged, built_pages=len(built_pages(staged.site_dir)), defects=defects
    )


# ── The stage ─────────────────────────────────────────────────────────────────


def _copy_pages(repo_root: Path, pages_dir: Path) -> None:
    """Copy `docs/` without the unpublished folders, the root documents and the nav file."""
    docs = repo_root / _DOCS_DIR

    def unpublished(directory: str, names: list[str]) -> set[str]:
        return set(names) & _UNPUBLISHED_DOCS if Path(directory) == docs else set()

    shutil.copytree(docs, pages_dir / _DOCS_DIR, ignore=unpublished)
    for name in (*SITE_ROOT_DOCUMENTS, _NAV_FILE):
        shutil.copy2(repo_root / name, pages_dir / name)


def _published_paths(pages_dir: Path) -> frozenset[str]:
    """The repository path of each staged file, and of each folder that has a page of its own."""
    files = [
        path.relative_to(pages_dir).as_posix() for path in pages_dir.rglob("*") if path.is_file()
    ]
    folders = [
        posixpath.dirname(name) or "."
        for name in files
        if posixpath.basename(name) in _FOLDER_PAGES
    ]
    return frozenset([*files, *folders])


def _staged_config(config: dict[str, Any], repo_root: Path, build: BuildData) -> dict[str, Any]:
    """The site settings with the stage folders, the theme overrides and the build data."""
    theme = dict(config.get("theme") or {})
    theme["custom_dir"] = str(repo_root / _OVERRIDES_DIR)
    extra = dict(config.get("extra") or {})
    extra["build"] = build.model_dump()
    return {
        **config,
        "docs_dir": _STAGED_PAGES,
        "site_dir": _STAGED_SITE,
        "theme": theme,
        "extra": extra,
    }


# ── The link change ───────────────────────────────────────────────────────────


class _GitHubLinks:
    """The GitHub link of each repository file that the site does not publish."""

    def __init__(
        self, repo_url: str, commit: str, repo_root: Path, published: frozenset[str]
    ) -> None:
        self._base = repo_url
        self._commit = commit
        self._root = repo_root
        self._published = published

    def target(self, destination: str, page: str, *, image: bool) -> str | None:
        """The GitHub link for `destination` on `page`, or None to keep the link as it is: a link
        with a scheme or a host, a link to a page of the site, and a link to no repository file."""
        parts = urlsplit(destination.removeprefix("<").removesuffix(">"))
        if parts.scheme or parts.netloc or not parts.path or parts.path.startswith("/"):
            return None
        path = posixpath.normpath(posixpath.join(posixpath.dirname(page), unquote(parts.path)))
        if path == ".." or path.startswith("../") or path in self._published:
            return None
        local = self._root / path
        if not local.exists():
            return None
        kind = "raw" if image else "tree" if local.is_dir() else "blob"
        link = f"{self._base}/{kind}/{self._commit}/{quote(path)}"
        query = f"?{parts.query}" if parts.query else ""
        fragment = f"#{parts.fragment}" if parts.fragment else ""
        return f"{link}{query}{fragment}"


def _rewrite_page(page: Path, pages_dir: Path, finder: _LinkFinder, links: _GitHubLinks) -> int:
    """Change the links of `page` to repository files outside the site, and count them."""
    source = page.read_bytes()
    name = page.relative_to(pages_dir).as_posix()
    chunks: list[bytes] = []
    last = 0
    for start, end, image in finder.destinations(source):
        target = links.target(source[start:end].decode("utf-8"), name, image=image)
        if target is None:
            continue
        chunks += [source[last:start], target.encode("utf-8")]
        last = end
    if not chunks:
        return 0
    page.write_bytes(b"".join([*chunks, source[last:]]))
    return len(chunks) // 2


class _LinkFinder:
    """The link and image destinations of a Markdown document, from tree-sitter-markdown."""

    def __init__(self) -> None:
        import tree_sitter_markdown
        from tree_sitter import Language, Parser, Query

        inline = Language(tree_sitter_markdown.inline_language())
        self._block = Parser(Language(tree_sitter_markdown.language()))
        self._inline = Parser(inline)
        self._query = Query(inline, _DESTINATION_QUERY)

    def destinations(self, source: bytes) -> list[tuple[int, int, bool]]:
        """The byte range of each link and image destination, and whether it is an image. A link
        in a code block or a code span is not a link.

        Each inline node is parsed on its own. One parse over all inline nodes as included ranges
        took 4.8 s on the 890 kB CHANGELOG.md and missed 12 of its links (2026-11-12).
        """
        from tree_sitter import QueryCursor

        found: list[tuple[int, int, bool]] = []
        for span in _inline_nodes(self._block.parse(source).root_node):
            offset = span.start_byte
            tree = self._inline.parse(source[offset : span.end_byte])
            for kind, nodes in QueryCursor(self._query).captures(tree.root_node).items():
                found += [
                    (offset + node.start_byte, offset + node.end_byte, kind == "image")
                    for node in nodes
                ]
        return sorted(found)


def _inline_nodes(root: Any) -> Iterator[Any]:
    """The inline nodes of a block tree, in document order."""
    waiting = [root]
    while waiting:
        node = waiting.pop()
        if node.type in _INLINE_NODES:
            yield node
        else:
            waiting.extend(reversed(node.children))


# ── The built site ────────────────────────────────────────────────────────────


def _page_key(path: str) -> str:
    """The URL path of a page folder or a nav link: `""` for the home page, else `a/b/`."""
    normal = posixpath.normpath(path or ".")
    return "" if normal == "." else f"{normal}/"


class _BuiltPage(HTMLParser):
    """The nav links and the build commit of one built page."""

    def __init__(self) -> None:
        super().__init__()
        self.nav_pages: set[str] = set()
        self.build_commit: str | None = None

    @classmethod
    def read(cls, path: Path, *, head_only: bool = False) -> _BuiltPage:
        html = path.read_text(encoding="utf-8")
        parser = cls()
        parser.feed(html.partition("</head>")[0] if head_only else html)
        parser.close()
        return parser

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "meta" and values.get("name") == BUILD_COMMIT_META:
            self.build_commit = values.get("content")
        if tag == "a" and _NAV_LINK_CLASS in (values.get("class") or "").split():
            href = urlsplit(values.get("href") or "")
            if not (href.scheme or href.netloc) and not (values.get("href") or "").startswith("#"):
                self.nav_pages.add(_page_key(href.path))
