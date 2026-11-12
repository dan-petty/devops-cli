"""A small repository with the sources of the docs site, and pages of a built site (#5152)."""

from __future__ import annotations

from pathlib import Path

SITE_SHA = "0123456789abcdef0123456789abcdef01234567"
SITE_CONFIG = """\
[project]
site_name = "site"
site_url = "https://example.com/site/"
repo_url = "https://github.com/example/site"
edit_uri = "edit/main/"

[project.theme]
features = ["navigation.tabs"]

[project.plugins.awesome-nav]
"""
SITE_ROOT_DOCUMENTS = (
    "ARCHITECTURE.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "RELEASE_CYCLE.md",
    "CONTEXT.md",
    "AGENTS.md",
    "CHANGELOG.md",
)


def write_files(root: Path, files: dict[str, str]) -> None:
    """Write each file of `files`, a map of a path under `root` to its text."""
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def write_site_repository(root: Path, readme: str = "# Site\n", guide: str = "# Guide\n") -> Path:
    """A repository with the site sources, the root documents and some files outside the site."""
    write_files(
        root,
        {
            "zensical.toml": SITE_CONFIG,
            ".nav.yml": "nav:\n  - README.md\n",
            "pyproject.toml": '[project]\nname = "site"\nversion = "1.2.3"\n',
            "overrides/main.html": '{% extends "base.html" %}\n',
            "README.md": readme,
            **{name: f"# {name}\n" for name in SITE_ROOT_DOCUMENTS},
            "docs/TESTING.md": "# Testing\n\n## Run time\n",
            "docs/guide/page.md": guide,
            "docs/assets/css/tokens-light.css": ":root {}\n",
            "docs/agent/README.md": "# Agent records\n",
            "src/x.py": "x = 1\n",
            "k8s/README.md": "# Manifests\n",
        },
    )
    return root


def built_page(nav: list[str], commit: str = SITE_SHA) -> str:
    """The HTML of a built page: the build commit tag, the nav links and one heading link."""
    links = "".join(f'<a href="{href}" class="md-nav__link">x</a>' for href in nav)
    return (
        f'<html><head><meta name="devops-build-commit" content="{commit}"></head>'
        f'<body><nav class="md-nav md-nav--primary">{links}'
        '<a href="#heading" class="md-nav__link">toc</a></nav></body></html>'
    )
