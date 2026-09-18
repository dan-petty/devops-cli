"""Release management and release cycle orchestration subcommands."""

from __future__ import annotations

import importlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import typer

from devops_cli.config.constants import (
    CONST_CHANGELOG_FILENAME,
    CONST_CONVENTIONAL_COMMIT_CATEGORIES,
    CONST_CONVENTIONAL_COMMIT_CATEGORY_ORDER,
    CONST_DOCS_DIR_NAME,
    CONST_GH_CLI,
    CONST_GIT_MAIN_BRANCH,
    CONST_INIT_PY_PATH,
    CONST_PYPROJECT_FILENAME,
    CONST_README_FILENAME,
)
from devops_cli.config.defaults import (
    DEFAULT_RELEASE_LABEL,
    DEFAULT_RELEASE_TYPE,
    DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
)
from devops_cli.core.cli import new_typer
from devops_cli.dry_run import is_dry_run, render_dry_run_result
from devops_cli.lang import HELP, MESSAGES

_LAZY_OBJECT_MAPPING: dict[str, tuple[str, str]] = {
    "DocGenerator": ("devops_cli.docs.generator", "DocGenerator"),
    "run_subprocess": ("devops_cli.core.process", "run_subprocess"),
    "run_gh": ("devops_cli.github.rate_limiter", "run_gh"),
    "print_error": ("devops_cli.output", "print_error"),
    "print_info": ("devops_cli.output", "print_info"),
    "print_success": ("devops_cli.output", "print_success"),
    "print_warning": ("devops_cli.output", "print_warning"),
    "print_table": ("devops_cli.output", "print_table"),
    "format_code_span": ("devops_cli.output", "format_code_span"),
}


def __getattr__(name: str) -> Any:
    if name in _LAZY_OBJECT_MAPPING:
        mod_path, obj_name = _LAZY_OBJECT_MAPPING[name]
        module = importlib.import_module(mod_path)
        return getattr(module, obj_name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _get(name: str) -> Any:
    mod_dict = sys.modules[__name__].__dict__
    if name in mod_dict:
        return mod_dict[name]
    if name in _LAZY_OBJECT_MAPPING:
        mod_path, obj_name = _LAZY_OBJECT_MAPPING[name]
        module = importlib.import_module(mod_path)
        return getattr(module, obj_name)
    return getattr(sys.modules[__name__], name)


app = new_typer(help=HELP.release.app)

_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$")


# =============================================================================
# Path & Git Inspection Helpers
# =============================================================================


def _get_project_root(target: Path | None = None) -> Path:
    """Find the top-level repository root containing pyproject.toml."""
    from devops_cli.core.repo import find_top_level_repo_root

    return find_top_level_repo_root(target)


def _resolve_safe_project_path(root: Path, relative_name: str | Path) -> Path:
    """Resolve a path and verify it strictly resides within repository root."""
    from devops_cli.core.repo import resolve_safe_subpath

    return resolve_safe_subpath(root, relative_name)


def _get_pyproject_version(root: Path) -> str | None:
    """Read version string from pyproject.toml."""
    pyproject_file = _resolve_safe_project_path(root, CONST_PYPROJECT_FILENAME)
    if not pyproject_file.exists():
        return None
    content = pyproject_file.read_text(encoding="utf-8")
    match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
    return match.group(1) if match else None


def _get_init_version(root: Path) -> str | None:
    """Read version from src/devops_cli/__init__.py or pyproject.toml."""
    init_file = _resolve_safe_project_path(root, CONST_INIT_PY_PATH)
    if not init_file.exists():
        return None
    content = init_file.read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
    if match:
        return match.group(1)
    return _get_pyproject_version(root)


def _get_latest_git_tag(root: Path) -> str | None:
    """Retrieve latest git tag if git is available."""
    from devops_cli.git.operations import get_latest_git_tag

    return get_latest_git_tag(root)


def _is_git_clean(root: Path) -> bool:
    """Check whether git working directory has uncommitted changes."""
    from devops_cli.git.operations import is_git_clean

    return is_git_clean(root)


# =============================================================================
# Version & Changelog Manipulation Helpers
# =============================================================================


def _extract_changelog_notes(root: Path, version: str) -> str | None:
    """Extract release notes for a specific version from CHANGELOG.md."""
    changelog_file = _resolve_safe_project_path(root, "CHANGELOG.md")
    if not changelog_file.exists():
        return None
    content = changelog_file.read_text(encoding="utf-8")
    cleaned_ver = version.lstrip("v")
    pattern = rf"^##\s+\[v?{re.escape(cleaned_ver)}\][^\n]*\n(.*?)(?=^##\s+\[|\Z)"
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
    return match.group(1).strip() if match else None


def _extract_docs_release_notes(root: Path, version: str) -> str | None:
    """Extract release notes for a specific version from docs/RELEASE_NOTES.md."""
    rel_notes_file = _resolve_safe_project_path(
        root, Path(CONST_DOCS_DIR_NAME) / "RELEASE_NOTES.md"
    )
    if not rel_notes_file.exists():
        return None
    content = rel_notes_file.read_text(encoding="utf-8")
    cleaned_ver = version.lstrip("v")
    pattern = rf"^##\s+[^\n]*?v?{re.escape(cleaned_ver)}\b[^\n]*\n(.*?)(?=^##\s+|\Z)"
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
    return match.group(1).strip() if match else None


_CONVENTIONAL_RE = re.compile(r"^([a-zA-Z]+)(?:\([^\)]+\))?!?:\s*(.*)$")
_RELEASE_COMMIT_RE = re.compile(r"^(?:feat|fix|chore)\(release\)!?:\s*", re.IGNORECASE)


def _categorize_commit_item(line: str) -> str:
    """Categorize commit item by conventional commit prefix."""
    match = _CONVENTIONAL_RE.match(line.strip())
    if match:
        prefix = match.group(1).lower()
        return CONST_CONVENTIONAL_COMMIT_CATEGORIES.get(prefix, "Other Changes")
    return "Other Changes"


def _extract_raw_commit_lines(raw_log: str) -> list[str]:
    """Extract individual bullet items or commit message lines from git log output."""
    raw_lines = [
        line.strip().lstrip("*- ").strip() for line in raw_log.splitlines() if line.strip()
    ]
    seen: set[str] = set()
    items: list[str] = []
    for line in raw_lines:
        if len(line) <= 4 or _RELEASE_COMMIT_RE.match(line):
            continue
        if line not in seen:
            seen.add(line)
            items.append(line)
    return items


def _format_categorized_notes(items: list[str], version: str) -> str:
    """Format extracted commit items into categorized markdown release notes."""
    cleaned_ver = version.lstrip("v")
    categories: dict[str, list[str]] = {k: [] for k in CONST_CONVENTIONAL_COMMIT_CATEGORY_ORDER}
    for item in items:
        cat = _categorize_commit_item(item)
        categories[cat].append(item)

    has_conventional = any(
        categories[cat] for cat in ("Added", "Fixed & Hardened", "Changed & Improved")
    )
    if not has_conventional:
        bullets = "\n".join(f"* {item}" for item in items)
        return f"### Changes in v{cleaned_ver}\n\n{bullets}"

    sections: list[str] = [f"### Changes in v{cleaned_ver}\n"]
    for cat in CONST_CONVENTIONAL_COMMIT_CATEGORY_ORDER:
        entries = categories[cat]
        if entries:
            bullet_list = "\n".join(f"- {entry}" for entry in entries)
            sections.append(f"### {cat}\n{bullet_list}\n")

    return "\n".join(sections).strip()


def _extract_git_commit_notes(root: Path, version: str) -> str | None:
    """Extract and categorize commit log messages and squash bodies as fallback release notes."""
    prev_tag = _get_latest_git_tag(root)
    log_args = [f"{prev_tag}..HEAD"] if prev_tag else ["-n", "20"]
    cmd = ["git", "log", *log_args, "--pretty=format:%B"]
    proc = _get("run_subprocess")(
        cmd,
        cwd=root,
        capture_output=True,
        check=False,
        quiet=True,
    )
    if proc.returncode != 0 or not proc.stdout or not proc.stdout.strip():
        fallback_cmd = ["git", "log", *log_args, "--pretty=format:* %s (%h)"]
        proc = _get("run_subprocess")(
            fallback_cmd,
            cwd=root,
            capture_output=True,
            check=False,
            quiet=True,
        )

    if proc.returncode == 0 and proc.stdout and proc.stdout.strip():
        items = _extract_raw_commit_lines(proc.stdout)
        if items:
            return _format_categorized_notes(items, version)
        cleaned_ver = version.lstrip("v")
        return f"### Changes in v{cleaned_ver}\n\n{proc.stdout.strip()}"
    return None


def _resolve_release_notes(root: Path, version: str) -> str | None:
    """Resolve release notes via CHANGELOG.md, docs/RELEASE_NOTES.md, or git commit history."""
    return (
        _extract_changelog_notes(root, version)
        or _extract_docs_release_notes(root, version)
        or _extract_git_commit_notes(root, version)
    )


def _get_latest_changelog_version(root: Path) -> str | None:
    """Extract the first/latest released version listed in CHANGELOG.md."""
    changelog_file = _resolve_safe_project_path(root, "CHANGELOG.md")
    if not changelog_file.exists():
        return None
    content = changelog_file.read_text(encoding="utf-8")
    match = re.search(r"^##\s+\[(\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?)\]", content, re.MULTILINE)
    return match.group(1) if match else None


def _update_pyproject_version(root: Path, new_version: str) -> bool:
    """Update version in pyproject.toml."""
    from devops_cli.output import write_text_file

    pyproject_file = _resolve_safe_project_path(root, CONST_PYPROJECT_FILENAME)
    if not pyproject_file.exists():
        return False
    content = pyproject_file.read_text(encoding="utf-8")
    new_content, count = re.subn(
        r'(version\s*=\s*["\'])[^"\']+(["\'])',
        rf"\g<1>{new_version}\g<2>",
        content,
        count=1,
    )
    if count > 0:
        write_text_file(pyproject_file, new_content)
        from devops_cli.config.metadata import load_project_metadata

        load_project_metadata.cache_clear()
        return True
    return False


def _update_init_version(root: Path, new_version: str) -> bool:
    """Update __version__ in src/devops_cli/__init__.py if hardcoded, or return True."""
    from devops_cli.output import write_text_file

    init_file = _resolve_safe_project_path(root, CONST_INIT_PY_PATH)
    if not init_file.exists():
        return False
    content = init_file.read_text(encoding="utf-8")
    match = re.search(r'(__version__\s*=\s*["\'])[^"\']+(["\'])', content)
    if not match:
        # Dynamically derived from pyproject.toml
        return True
    new_content, count = re.subn(
        r'(__version__\s*=\s*["\'])[^"\']+(["\'])',
        rf"\g<1>{new_version}\g<2>",
        content,
        count=1,
    )
    if count > 0:
        write_text_file(init_file, new_content)
        return True
    return True


def _build_changelog_section(root: Path, new_version: str, today: str) -> str:
    """Build a complete changelog markdown section for a release version."""
    compiled_notes = _extract_git_commit_notes(root, new_version)
    if compiled_notes:
        notes_body = re.sub(r"^###\s+Changes in v[^\n]+\n*", "", compiled_notes).strip()
        if notes_body:
            return f"## [{new_version}] - {today}\n\n{notes_body}\n\n"
    return f"## [{new_version}] - {today}\n\n### Added\n- Release version {new_version}.\n\n"


def _update_changelog_header(root: Path, new_version: str, release_date: str | None = None) -> bool:
    """Ensure CHANGELOG.md has a header for the new version."""
    from devops_cli.output import write_text_file

    changelog_file = _resolve_safe_project_path(root, CONST_CHANGELOG_FILENAME)
    if not changelog_file.exists():
        return False
    today = release_date or datetime.now(UTC).strftime("%Y-%m-%d")
    content = changelog_file.read_text(encoding="utf-8")

    # If version already present in changelog, update date and populate if empty
    if f"## [{new_version}]" in content:
        current_notes = _extract_changelog_notes(root, new_version)
        if current_notes:
            new_content = re.sub(
                rf"##\s+\[{re.escape(new_version)}\]\s*(?:-\s*\d{{4}}-\d{{2}}-\d{{2}})?",
                f"## [{new_version}] - {today}",
                content,
            )
        else:
            section = _build_changelog_section(root, new_version, today)
            pattern = rf"##\s+\[{re.escape(new_version)}\][^\n]*(?:\n\s*)*"
            new_content = re.sub(pattern, section, content, count=1)
        write_text_file(changelog_file, new_content)
        return True

    # If [Unreleased] section exists, rename to [new_version] - date
    if "## [Unreleased]" in content:
        unreleased_notes = _extract_changelog_notes(root, "Unreleased")
        if unreleased_notes:
            new_content = content.replace(
                "## [Unreleased]",
                f"## [{new_version}] - {today}",
                1,
            )
        else:
            section = _build_changelog_section(root, new_version, today)
            new_content = re.sub(r"##\s+\[Unreleased\][^\n]*(?:\n\s*)*", section, content, count=1)
        write_text_file(changelog_file, new_content)
        return True

    # Otherwise prepend new section before the first ## [
    first_section = re.search(r"^##\s+\[", content, re.MULTILINE)
    if first_section:
        pos = first_section.start()
        section = _build_changelog_section(root, new_version, today)
        new_content = content[:pos] + section + content[pos:]
        write_text_file(changelog_file, new_content)
        return True

    return False


def _format_release_title(
    version: str, prefix: str = DEFAULT_RELEASE_TYPE, breaking: bool = False
) -> str:
    """Format release title with conventional commit: <feat|fix>(release)<!>: vx.x.x"""
    clean_ver = version.lstrip("v").strip()

    norm_prefix = prefix.lower().strip() if prefix else "feat"
    if norm_prefix not in ("feat", "fix"):
        norm_prefix = "feat"
    bang = "!" if breaking else ""
    return f"{norm_prefix}(release){bang}: v{clean_ver}"


# =============================================================================
# Command: release status
# =============================================================================


def _build_status_table(repo_root: Path) -> Any:
    """Build the Rich table representation of current release status."""
    pyproject_ver = _get_pyproject_version(repo_root) or "unknown"
    init_ver = _get_init_version(repo_root) or "unknown"
    latest_tag = _get_latest_git_tag(repo_root) or "none"
    latest_cl_ver = _get_latest_changelog_version(repo_root) or "none"
    clean_tree = _is_git_clean(repo_root)

    generator = _get("DocGenerator")(root_dir=repo_root)
    docs_up_to_date, _ = generator.check_docs(repo_root / "docs", check_readme_table=True)

    rows = [
        ["pyproject.toml Version", pyproject_ver],
        ["src/devops_cli/__init__.py", init_ver],
        [
            "Version Consistency",
            "[green]✓ MATCH[/green]" if pyproject_ver == init_ver else "[red]✗ MISMATCH[/red]",
        ],
        ["Latest Git Tag", latest_tag],
        ["Latest CHANGELOG Version", latest_cl_ver],
        [
            "Working Tree Clean",
            "[green]✓ Clean[/green]" if clean_tree else "[yellow]⚠ Uncommitted Changes[/yellow]",
        ],
        [
            "Documentation Synchronized",
            (
                "[green]✓ Synchronized[/green]"
                if docs_up_to_date
                else "[red]✗ Outdated (run 'devops docs generate')[/red]"
            ),
        ],
    ]

    from devops_cli.output import render_table

    return render_table(
        title=MESSAGES.release.status_header,
        columns=[("Property", "bold"), ("Value", "green")],
        rows=rows,
        border_style="cyan",
    )


# =============================================================================
# Command: release status
# =============================================================================


@app.command("status")
def release_status(
    root: Annotated[
        Path | None,
        typer.Option("--root", "-r", help=HELP.options.root),
    ] = None,
    watch: Annotated[
        bool,
        typer.Option("--watch", "-w", help="Continuously monitor release state in real-time."),
    ] = False,
    interval: Annotated[
        float,
        typer.Option("--interval", "-i", help="Watcher auto-refresh polling interval in seconds."),
    ] = 2.0,
) -> None:
    """Display current release status, versions, tags, changelog, and docs state."""
    repo_root = _get_project_root(root)
    if watch:
        from devops_cli.watchers.live_resource import LiveResourceWatcher

        watcher = LiveResourceWatcher(
            lambda: _build_status_table(repo_root),
            interval_seconds=interval,
            name="release_status",
        )
        watcher.watch()
        return

    table = _build_status_table(repo_root)
    _get("print_table")(table)


# =============================================================================
# Command: release prepare
# =============================================================================


@app.command("prepare")
def release_prepare(
    version: Annotated[str, typer.Argument(help=HELP.release.target_version)],
    sync_docs: Annotated[
        bool,
        typer.Option(
            "--sync-docs/--no-sync-docs",
            help=HELP.release.sync_docs,
        ),
    ] = True,
    update_changelog: Annotated[
        bool,
        typer.Option(
            "--changelog/--no-changelog",
            help=HELP.release.ensure_changelog,
        ),
    ] = True,
    create_pr: Annotated[
        bool,
        typer.Option(
            "--create-pr",
            "-p",
            help=HELP.release.auto_pr,
        ),
    ] = False,
    release_type: Annotated[
        str,
        typer.Option(
            "--type",
            "-t",
            help=HELP.release.prefix,
        ),
    ] = DEFAULT_RELEASE_TYPE,
    breaking: Annotated[
        bool,
        typer.Option(
            "--breaking",
            "-b",
            help=HELP.release.breaking,
        ),
    ] = False,
    draft: Annotated[
        bool,
        typer.Option(
            "--draft/--no-draft",
            help=HELP.options.draft,
        ),
    ] = True,
    root: Annotated[
        Path | None,
        typer.Option("--root", "-r", help=HELP.options.root),
    ] = None,
) -> None:
    """Bump version across pyproject.toml and source, update changelog, and sync docs."""
    clean_version = version.lstrip("v").strip()
    if not _SEMVER_RE.match(clean_version):
        _get("print_error")(MESSAGES.release.invalid_version.format(version=version), prefix=False)
        raise typer.Exit(1)

    repo_root = _get_project_root(root)

    if is_dry_run():
        render_dry_run_result(
            command="devops release prepare",
            action="prepare_release_version",
            target=clean_version,
            details={
                "version": clean_version,
                "pyproject_target": str(repo_root / CONST_PYPROJECT_FILENAME),
                "init_target": str(repo_root / "src/devops_cli/__init__.py"),
                "sync_docs": sync_docs,
                "update_changelog": update_changelog,
                "create_pr": create_pr,
                "draft": draft,
                "release_type": release_type,
                "breaking": breaking,
            },
        )
        if create_pr:
            render_dry_run_result(
                command="devops release pr",
                action="create_release_pull_request",
                target=clean_version,
                details={
                    "version": clean_version,
                    "branch": f"release/v{clean_version}",
                    "base": "main",
                    "draft": draft,
                    "labels": "release",
                    "push": True,
                    "release_type": release_type,
                    "breaking": breaking,
                },
            )
        return

    _get("print_info")(
        MESSAGES.release.preparing_release.format(version=clean_version), prefix=False
    )

    # 1. Update pyproject.toml
    if _update_pyproject_version(repo_root, clean_version):
        _get("print_info")(
            MESSAGES.release.updated_pyproject.format(version=clean_version), prefix=False
        )

    # 2. Update __init__.py
    if _update_init_version(repo_root, clean_version):
        _get("print_info")(
            MESSAGES.release.updated_init.format(version=clean_version), prefix=False
        )

    # 3. Update CHANGELOG.md
    if update_changelog:
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        if _update_changelog_header(repo_root, clean_version, today):
            _get("print_info")(
                MESSAGES.release.updated_changelog.format(version=clean_version, date=today),
                prefix=False,
            )

    # 4. Regenerate documentation & sync README Command Matrix
    if sync_docs:
        generator = _get("DocGenerator")(root_dir=repo_root)
        generator.write_all_docs(output_dir=repo_root / "docs", sync_readme_table=True)
    msg = f"Release preparation for v{clean_version} completed successfully."
    _get("print_success")(msg)

    if create_pr:
        release_pr(
            version=clean_version,
            draft=draft,
            release_type=release_type,
            breaking=breaking,
            root=root,
        )


# =============================================================================
# Command: release pr
# =============================================================================


def _validate_release_version(version: str | None, repo_root: Path) -> str:
    """Validate and normalize release semantic version string."""
    target_ver = (version or _get_pyproject_version(repo_root) or "").lstrip("v").strip()
    if not target_ver or not _SEMVER_RE.match(target_ver):
        err = MESSAGES.release.invalid_version.format(version=target_ver or version or "")
        _get("print_error")(err, prefix=False)
        raise typer.Exit(1)
    return target_ver


def _checkout_release_branch(branch_name: str, repo_root: Path) -> None:
    """Checkout a new or existing git release branch."""
    _get("print_info")(
        MESSAGES.release.creating_release_branch.format(branch=branch_name), prefix=False
    )
    proc = _get("run_subprocess")(["git", "checkout", "-B", branch_name], cwd=repo_root)
    if proc.returncode != 0:
        _get("print_error")(
            f"Failed to create release branch {branch_name}: {proc.stderr}", prefix=False
        )
        raise typer.Exit(1)
    _get("print_success")(MESSAGES.release.branch_created.format(branch=branch_name), prefix=False)


def _commit_and_push_release_branch(
    branch_name: str, release_title: str, push: bool, repo_root: Path
) -> None:
    """Stage release files, create release commit, and optionally push to remote."""
    _get("run_subprocess")(
        [
            "git",
            "add",
            CONST_PYPROJECT_FILENAME,
            str(CONST_INIT_PY_PATH),
            "CHANGELOG.md",
            CONST_README_FILENAME,
            f"{CONST_DOCS_DIR_NAME}/",
        ],
        cwd=repo_root,
    )
    commit_proc = _get("run_subprocess")(["git", "commit", "-m", release_title], cwd=repo_root)
    if commit_proc.returncode != 0 and "nothing to commit" not in str(commit_proc.stdout):
        _get("print_warning")(f"Note: {commit_proc.stderr or commit_proc.stdout}", prefix=False)

    if push:
        push_proc = _get("run_subprocess")(
            ["git", "push", "-u", "origin", branch_name], cwd=repo_root
        )
        if push_proc.returncode != 0:
            _get("print_warning")(
                f"Warning: Could not push branch to remote: {push_proc.stderr}", prefix=False
            )


def _query_gh_milestone_issues(repo_root: Path, milestone_tag: str) -> list[str]:
    """Query GitHub milestone issues via rate-managed run_gh."""
    try:
        run_gh_fn = _get("run_gh")
        proc = run_gh_fn(
            [
                "issue",
                "list",
                "--milestone",
                milestone_tag,
                "--json",
                "number,title,labels,state",
                "--limit",
                "50",
            ],
            cwd=repo_root,
            quiet=True,
            use_cache=False,
        )
        if proc.returncode == 0 and proc.stdout:
            raw_issues = json.loads(proc.stdout)
            return [f"- #{iss['number']}" for iss in raw_issues if iss.get("number")]
    except Exception:
        pass
    return []


def _query_branch_commit_deliverables(repo_root: Path, base: str, branch_name: str) -> list[str]:
    """Extract branch commit messages as fallback release deliverables."""
    try:
        log_proc = _get("run_subprocess")(
            ["git", "log", f"{base}..{branch_name}", "--pretty=format:* %s (%h)"],
            cwd=repo_root,
            quiet=True,
        )
        if log_proc.returncode == 0 and log_proc.stdout:
            return [f"- {line}" for line in _extract_raw_commit_lines(log_proc.stdout)]
    except Exception:
        pass
    return []


def _fetch_milestone_deliverables(
    repo_root: Path,
    target_ver: str,
    base: str = CONST_GIT_MAIN_BRANCH,
    branch_name: str | None = None,
) -> list[str]:
    """Fetch milestone issues and branch commits for release PR deliverable tracking."""
    milestone_tag = f"v{target_ver.lstrip('v')}"
    deliverables = _query_gh_milestone_issues(repo_root, milestone_tag)
    if not deliverables and branch_name:
        return _query_branch_commit_deliverables(repo_root, base, branch_name)
    return deliverables


def _is_stale_duplicate_changelog(repo_root: Path, cleaned_ver: str, notes: str) -> bool:
    """Check if extracted changelog notes are duplicated from the immediately preceding release."""
    changelog_file = _resolve_safe_project_path(repo_root, CONST_CHANGELOG_FILENAME)
    if not changelog_file.exists():
        return False
    content = changelog_file.read_text(encoding="utf-8")
    all_vers = re.findall(r"^##\s+\[(\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?)\]", content, re.MULTILINE)
    matched_vers = [v[0] if isinstance(v, tuple) else v for v in all_vers]
    if cleaned_ver not in matched_vers:
        return False
    idx = matched_vers.index(cleaned_ver)
    if idx + 1 >= len(matched_vers):
        return False
    prev_notes = _extract_changelog_notes(repo_root, matched_vers[idx + 1])
    return bool(prev_notes and prev_notes.strip() == notes.strip())


def _extract_branch_release_notes(
    repo_root: Path, base: str, branch_name: str, cleaned_ver: str
) -> str | None:
    """Extract and categorize release notes from branch commits relative to base."""
    try:
        log_proc = _get("run_subprocess")(
            ["git", "log", f"{base}..{branch_name}", "--pretty=format:%B"],
            cwd=repo_root,
            quiet=True,
        )
        if log_proc.returncode == 0 and log_proc.stdout and log_proc.stdout.strip():
            items = _extract_raw_commit_lines(log_proc.stdout)
            if items:
                return _format_categorized_notes(items, cleaned_ver)
    except Exception:
        pass
    return None


def _resolve_clean_release_notes(
    repo_root: Path,
    target_ver: str,
    base: str = CONST_GIT_MAIN_BRANCH,
    branch_name: str | None = None,
) -> str:
    """Resolve clean, non-duplicate release notes for release PR description."""
    cleaned_ver = target_ver.lstrip("v")
    notes = _extract_changelog_notes(repo_root, cleaned_ver)
    if notes and not _is_stale_duplicate_changelog(repo_root, cleaned_ver, notes):
        return notes.strip()

    if branch_name:
        branch_notes = _extract_branch_release_notes(repo_root, base, branch_name, cleaned_ver)
        if branch_notes:
            return branch_notes

    return f"### Added\n- Initial release branch preparation and quality certification for v{cleaned_ver}."


def _build_quality_checklist(branch_name: str, draft: bool) -> str:
    """Build standardized 10-gate quality checklist for release PR."""
    pr_checked = " " if draft else "x"
    return (
        "### Quality Gate Checklist\n"
        f"- [{pr_checked}] 10-Gate CI Quality Gate passing (`devops ci`)\n"
        f"- [{pr_checked}] Documentation and Command Matrix in `README.md` synchronized\n"
        f"- [{pr_checked}] Version matching across `pyproject.toml` and `src/devops_cli/__init__.py`\n"
        f"- [{pr_checked}] CodeQL & Static Analysis passing\n"
        f"- [{pr_checked}] Pre-commit & CI validation passing\n"
        f"- [{pr_checked}] Milestone deliverables reviewed and merged into `{branch_name}`\n"
        f"- [{pr_checked}] Final release readiness verified before converting from draft"
    )


def _build_release_pr_body(
    repo_root: Path,
    target_ver: str,
    base: str,
    branch_name: str,
    draft: bool,
    pr_title: str,
) -> str:
    """Build authoritative markdown description for release pull request."""
    cleaned_ver = target_ver.lstrip("v")
    deliverables = _fetch_milestone_deliverables(repo_root, cleaned_ver, base, branch_name)
    notes = _resolve_clean_release_notes(repo_root, cleaned_ver, base, branch_name)
    checklist = _build_quality_checklist(branch_name, draft)

    sections = [
        f"## {pr_title}",
        f"### Summary\nRelease `v{cleaned_ver}` tracking PR under GitHub pull request merge controls.",
    ]

    if deliverables:
        heading = "### Target Milestone Deliverables" if draft else "### Included Deliverables"
        sections.append(f"{heading}\n" + "\n".join(deliverables))

    if notes:
        sections.append(f"### Release Notes\n{notes}")

    sections.append(checklist)
    return "\n\n".join(sections).strip() + "\n"


def _build_release_pr_command(
    pr_title: str,
    pr_body: str,
    base: str,
    branch_name: str,
    draft: bool,
    labels: str,
) -> list[str]:
    """Construct command argument list for opening release pull request."""
    pr_cmd = [
        CONST_GH_CLI,
        "pr",
        "create",
        "--title",
        pr_title,
        "--body",
        pr_body,
        "--base",
        base,
        "--head",
        branch_name,
    ]
    if draft:
        pr_cmd.append("--draft")
    if labels:
        cleaned_labels = [lbl.strip() for lbl in labels.split(",") if lbl.strip()]
        for lbl in cleaned_labels:
            if not re.match(r"^[a-zA-Z0-9_\- /.:]+$", lbl):
                _get("print_error")(f"Invalid label '{lbl}'.", prefix=False)
                raise typer.Exit(1)
            pr_cmd.extend(["--label", lbl])
    return pr_cmd


def _execute_release_pr(
    pr_cmd: list[str],
    branch_name: str,
    labels: str,
    repo_root: Path,
) -> None:
    """Execute gh pr create with label fallback if labels fail."""
    run_gh_fn = _get("run_gh")
    pr_proc = run_gh_fn(pr_cmd, cwd=repo_root)
    if pr_proc.returncode != 0 and labels and "label" in (pr_proc.stderr or "").lower():
        fallback_cmd = [
            arg
            for idx, arg in enumerate(pr_cmd)
            if arg != "--label" and (idx == 0 or pr_cmd[idx - 1] != "--label")
        ]
        pr_proc = run_gh_fn(fallback_cmd, cwd=repo_root)

    if pr_proc.returncode == 0:
        pr_url = str(pr_proc.stdout).strip()
        _get("print_success")(MESSAGES.release.pr_created.format(url=pr_url), prefix=False)
    else:
        err = str(pr_proc.stderr).strip() or str(pr_proc.stdout).strip()
        _get("print_warning")(MESSAGES.release.pr_failed.format(error=err), prefix=False)
        _get("print_info")(
            f"Branch '{branch_name}' is ready. You can manually open the PR on GitHub.",
            prefix=False,
        )


@app.command("pr")
def release_pr(
    version: Annotated[
        str | None,
        typer.Option("--version", "-v", help=HELP.options.version),
    ] = None,
    base: Annotated[
        str,
        typer.Option("--base", "-b", help=HELP.options.base_branch),
    ] = CONST_GIT_MAIN_BRANCH,
    draft: Annotated[
        bool,
        typer.Option("--draft/--no-draft", help=HELP.options.draft),
    ] = True,
    labels: Annotated[
        str,
        typer.Option("--labels", "-l", help=HELP.options.labels),
    ] = DEFAULT_RELEASE_LABEL,
    push: Annotated[
        bool,
        typer.Option("--push/--no-push", help=HELP.options.push),
    ] = True,
    release_type: Annotated[
        str,
        typer.Option(
            "--type",
            "-t",
            help=HELP.release.prefix,
        ),
    ] = DEFAULT_RELEASE_TYPE,
    breaking: Annotated[
        bool,
        typer.Option(
            "--breaking",
            "-b",
            help=HELP.release.breaking,
        ),
    ] = False,
    root: Annotated[
        Path | None,
        typer.Option("--root", "-r", help=HELP.options.root),
    ] = None,
) -> None:
    """Create release branch, commit version bumps, and open a GitHub Release Pull Request."""
    repo_root = _get_project_root(root)
    target_ver = _validate_release_version(version, repo_root)
    branch_name = f"release/v{target_ver}"
    release_title = _format_release_title(target_ver, prefix=release_type, breaking=breaking)

    if is_dry_run():
        render_dry_run_result(
            command="devops release pr",
            action="create_release_pull_request",
            target=target_ver,
            details={
                "version": target_ver,
                "branch": branch_name,
                "base": base,
                "draft": draft,
                "labels": labels,
                "push": push,
                "release_type": release_type,
                "breaking": breaking,
                "title": release_title,
            },
        )
        return

    _checkout_release_branch(branch_name, repo_root)
    _commit_and_push_release_branch(branch_name, release_title, push, repo_root)

    _get("print_info")(
        MESSAGES.release.creating_release_pr.format(version=target_ver), prefix=False
    )
    pr_title = release_title
    pr_body = _build_release_pr_body(
        repo_root=repo_root,
        target_ver=target_ver,
        base=base,
        branch_name=branch_name,
        draft=draft,
        pr_title=pr_title,
    )

    pr_cmd = _build_release_pr_command(
        pr_title=pr_title,
        pr_body=pr_body,
        base=base,
        branch_name=branch_name,
        draft=draft,
        labels=labels,
    )
    _execute_release_pr(
        pr_cmd=pr_cmd,
        branch_name=branch_name,
        labels=labels,
        repo_root=repo_root,
    )


# =============================================================================
# Command: release check
# =============================================================================


def _verify_release_versions(repo_root: Path) -> str:
    """Verify version consistency across pyproject.toml, __init__.py, and CHANGELOG.md."""
    pyproject_ver = _get_pyproject_version(repo_root)
    init_ver = _get_init_version(repo_root)
    changelog_ver = _get_latest_changelog_version(repo_root)

    if not pyproject_ver or pyproject_ver != init_ver:
        _get("print_error")(
            f"Version mismatch: pyproject.toml ({pyproject_ver}) != "
            f"src/devops_cli/__init__.py ({init_ver})",
            prefix=False,
        )
        raise typer.Exit(1)

    if not changelog_ver or changelog_ver != pyproject_ver:
        _get("print_error")(
            f"Version mismatch: CHANGELOG.md ({changelog_ver or 'missing'}) does not match "
            f"pyproject.toml ({pyproject_ver}). Update CHANGELOG.md before releasing.",
            prefix=False,
        )
        raise typer.Exit(1)

    changelog_notes = _extract_changelog_notes(repo_root, pyproject_ver)
    if not changelog_notes:
        _get("print_error")(
            f"CHANGELOG.md entry for v{pyproject_ver} is empty. "
            "Populate release notes before releasing.",
            prefix=False,
        )
        raise typer.Exit(1)

    return pyproject_ver


def _verify_release_docs(repo_root: Path) -> None:
    """Verify documentation freshness before releasing."""
    generator = _get("DocGenerator")(root_dir=repo_root)
    docs_ok, diffs = generator.check_docs(repo_root / "docs", check_readme_table=True)
    if not docs_ok:
        _get("print_error")(
            "Documentation is out of sync. "
            "Run 'devops release prepare' or 'devops docs generate --sync-readme'",
            prefix=False,
        )
        for d in diffs:
            _get("print_error")(f"  - {d}", prefix=False)
        raise typer.Exit(1)


def _run_release_ci_gate(
    repo_root: Path, pyproject_ver: str, skip_ci: bool, allow_dirty: bool
) -> None:
    """Execute release CI gate checks or render dry-run summary."""
    if skip_ci:
        return

    if is_dry_run():
        render_dry_run_result(
            command="devops release check",
            action="verify_release_readiness",
            target=pyproject_ver,
            details={
                "version": pyproject_ver,
                "skip_ci": skip_ci,
                "allow_dirty": allow_dirty,
                "status": "VERIFIED_DRY_RUN",
            },
        )
        return

    _get("print_info")("Running CI quality gate...", prefix=False)
    proc = _get("run_subprocess")(
        ["uv", "run", "devops", "ci", "run"],
        cwd=repo_root,
        capture_output=False,
        timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS * 4,
    )
    if proc.returncode != 0:
        _get("print_error")(
            "CI Quality Gate checks failed. Resolve errors before releasing.", prefix=False
        )
        raise typer.Exit(1)


@app.command("check")
def release_check(
    skip_ci: Annotated[
        bool,
        typer.Option("--skip-ci", help=HELP.release.skip_ci),
    ] = False,
    allow_dirty: Annotated[
        bool,
        typer.Option("--allow-dirty", help=HELP.release.allow_dirty),
    ] = False,
    root: Annotated[
        Path | None,
        typer.Option("--root", "-r", help=HELP.options.root),
    ] = None,
) -> None:
    """Verify release readiness (version consistency, docs freshness, and CI quality gates)."""
    repo_root = _get_project_root(root)
    pyproject_ver = _verify_release_versions(repo_root)

    if not allow_dirty and not _is_git_clean(repo_root):
        _get("print_error")(
            "Git working directory is dirty. Commit or stash changes before releasing.",
            prefix=False,
        )
        raise typer.Exit(1)

    _verify_release_docs(repo_root)
    _run_release_ci_gate(repo_root, pyproject_ver, skip_ci, allow_dirty)
    _get("print_success")(MESSAGES.release.verification_passed, prefix=False)


# =============================================================================
# Command: release notes
# =============================================================================


@app.command("notes")
def release_notes(
    version: Annotated[
        str | None,
        typer.Option("--version", "-v", help=HELP.options.version),
    ] = None,
    raw: Annotated[
        bool,
        typer.Option("--raw", help=HELP.options.raw),
    ] = False,
    root: Annotated[
        Path | None,
        typer.Option("--root", "-r", help=HELP.options.root),
    ] = None,
) -> None:
    """Print markdown release notes for a specified or current release version."""
    from devops_cli.output import (
        print_error,
        print_panel,
        print_warning,
        write_stdout,
    )

    repo_root = _get_project_root(root)
    target_ver = (version or _get_pyproject_version(repo_root) or "").lstrip("v")
    if not target_ver:
        print_error("Could not determine target release version.", prefix=False)
        raise typer.Exit(1)

    notes = _resolve_release_notes(repo_root, target_ver)
    if not notes:
        print_warning(MESSAGES.release.notes_not_found.format(version=target_ver), prefix=False)
        raise typer.Exit(1)

    if is_dry_run():
        render_dry_run_result(
            command="devops release notes",
            action="extract_release_notes",
            target=target_ver,
            details={"version": target_ver, "raw": raw, "notes": notes},
        )
        return

    if raw:
        write_stdout(notes + "\n")
        return

    print_panel(
        notes,
        title=f"Release Notes — v{target_ver}",
        border_style="cyan",
    )


# =============================================================================
# Command: release changelog
# =============================================================================


@app.command("changelog")
def release_changelog(
    version: Annotated[
        str | None,
        typer.Option("--version", "-v", help=HELP.release.target_version),
    ] = None,
    update: Annotated[
        bool,
        typer.Option("--update", "-u", help=HELP.release.changelog_update),
    ] = False,
    from_tag: Annotated[
        str | None,
        typer.Option("--from-tag", help=HELP.release.changelog_from_tag),
    ] = None,
    raw: Annotated[
        bool,
        typer.Option("--raw", help=HELP.options.raw),
    ] = False,
    root: Annotated[
        Path | None,
        typer.Option("--root", "-r", help=HELP.options.root),
    ] = None,
) -> None:
    """Compile and generate changelog entries from git commits or PR deliverables."""
    from devops_cli.output import (
        print_error,
        print_panel,
        print_success,
        write_stdout,
    )

    repo_root = _get_project_root(root)
    target_ver = (version or _get_pyproject_version(repo_root) or "").lstrip("v")
    if not target_ver:
        print_error("Could not determine target release version.", prefix=False)
        raise typer.Exit(1)

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    compiled_notes = (
        _extract_git_commit_notes(repo_root, target_ver)
        or f"### Changes in v{target_ver}\n\n* Release v{target_ver}"
    )

    if is_dry_run():
        render_dry_run_result(
            command="devops release changelog",
            action="compile_release_changelog",
            target=target_ver,
            details={"version": target_ver, "update": update, "raw": raw, "from_tag": from_tag},
        )
        return

    if update:
        if _update_changelog_header(repo_root, target_ver, today):
            print_success(
                MESSAGES.release.updated_changelog.format(version=target_ver, date=today),
                prefix=False,
            )
        return

    if raw:
        write_stdout(compiled_notes + "\n")
        return

    print_panel(
        compiled_notes,
        title=f"Changelog — v{target_ver}",
        border_style="cyan",
    )


# =============================================================================
# Command: release tag
# =============================================================================


def _commit_release_tag_changes(repo_root: Path, release_title: str) -> None:
    """Stage release files and create commit before tagging."""
    _get("run_subprocess")(
        [
            "git",
            "add",
            CONST_PYPROJECT_FILENAME,
            str(CONST_INIT_PY_PATH),
            CONST_CHANGELOG_FILENAME,
            CONST_README_FILENAME,
            f"{CONST_DOCS_DIR_NAME}/",
        ],
        cwd=repo_root,
    )
    _get("run_subprocess")(
        ["git", "commit", "-m", release_title],
        cwd=repo_root,
    )


def _push_git_tag(repo_root: Path, tag_name: str, target_ver: str) -> None:
    """Push annotated tag to origin and close release milestone."""
    push_proc = _get("run_subprocess")(["git", "push", "origin", "--tags"], cwd=repo_root)
    if push_proc.returncode != 0:
        _get("print_error")(
            f"Failed to push tag {tag_name} to origin: {push_proc.stderr}", prefix=False
        )
        raise typer.Exit(1)
    _get("print_success")(MESSAGES.release.tag_pushed.format(tag=tag_name), prefix=False)
    _close_release_milestone_safe(repo_root, target_ver)


@app.command("tag")
def release_tag(
    version: Annotated[
        str | None,
        typer.Option("--version", "-v", help=HELP.options.version),
    ] = None,
    push: Annotated[
        bool,
        typer.Option("--push", "-p", help=HELP.options.push),
    ] = False,
    release_type: Annotated[
        str,
        typer.Option(
            "--type",
            "-t",
            help=HELP.release.prefix,
        ),
    ] = DEFAULT_RELEASE_TYPE,
    breaking: Annotated[
        bool,
        typer.Option(
            "--breaking",
            "-b",
            help=HELP.release.breaking,
        ),
    ] = False,
    message: Annotated[
        str | None,
        typer.Option("--message", "-m", help=HELP.release.tag_message),
    ] = None,
    root: Annotated[
        Path | None,
        typer.Option("--root", "-r", help=HELP.options.root),
    ] = None,
) -> None:
    """Create release commit and annotated git tag."""
    repo_root = _get_project_root(root)
    target_ver = _validate_release_version(version, repo_root)

    tag_name = f"v{target_ver}"
    release_title = _format_release_title(target_ver, prefix=release_type, breaking=breaking)
    tag_msg = message or release_title

    if is_dry_run():
        render_dry_run_result(
            command="devops release tag",
            action="create_annotated_git_tag",
            target=tag_name,
            details={
                "version": target_ver,
                "tag": tag_name,
                "message": tag_msg,
                "push": push,
                "release_type": release_type,
                "breaking": breaking,
                "title": release_title,
            },
        )
        return

    _commit_release_tag_changes(repo_root, release_title)

    # Create annotated tag
    tag_proc = _get("run_subprocess")(["git", "tag", "-a", tag_name, "-m", tag_msg], cwd=repo_root)
    if tag_proc.returncode != 0:
        _get("print_error")(f"Failed to create git tag {tag_name}: {tag_proc.stderr}", prefix=False)
        raise typer.Exit(1)

    _get("print_success")(MESSAGES.release.tag_created.format(tag=tag_name), prefix=False)

    if push:
        _push_git_tag(repo_root, tag_name, target_ver)


def _close_release_milestone_safe(repo_root: Path, version: str) -> None:
    """Attempt to close the repository release milestone without raising on network or auth failure."""
    try:
        from devops_cli.commands.gh import (
            _close_milestone_gh_cli,
            _get_github_client,
            _resolve_repo,
        )
        from devops_cli.github.milestones import close_repository_milestone

        target_repo = _resolve_repo()
        client = _get_github_client()
        ok = (
            close_repository_milestone(client, target_repo, version)
            if client
            else _close_milestone_gh_cli(target_repo, version)
        )
        if ok:
            _get("print_success")(
                f"Closed release milestone for v{version.lstrip('v')}.", prefix=False
            )
    except Exception as exc:
        _get("print_warning")(
            f"Note: Could not close milestone for v{version}: {exc}", prefix=False
        )
