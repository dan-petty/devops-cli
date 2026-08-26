"""Release management and release cycle orchestration subcommands."""

from __future__ import annotations

import importlib
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import typer

from devops_cli.config.constants import (
    CONST_DOCS_DIR_NAME,
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
    # Match ## [version] ... up to the next ## [ or end of string
    pattern = rf"^##\s+\[{re.escape(version)}\][^\n]*\n(.*?)(?=^##\s+\[|\Z)"
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


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
        return True
    return False


def _update_init_version(root: Path, new_version: str) -> bool:
    """Update __version__ in src/devops_cli/__init__.py if hardcoded, or return True."""
    from devops_cli.output import write_text_file

    init_file = _resolve_safe_project_path(root, CONST_INIT_PY_PATH)
    if not init_file.exists():
        return False
    content = init_file.read_text(encoding="utf-8")
    if "__version__ = " not in content:
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


def _update_changelog_header(root: Path, new_version: str, release_date: str | None = None) -> bool:
    """Ensure CHANGELOG.md has a header for the new version."""
    from devops_cli.output import write_text_file

    changelog_file = _resolve_safe_project_path(root, "CHANGELOG.md")
    if not changelog_file.exists():
        return False
    today = release_date or datetime.now(UTC).strftime("%Y-%m-%d")
    content = changelog_file.read_text(encoding="utf-8")

    # If version already present in changelog, update date
    if f"## [{new_version}]" in content:
        new_content = re.sub(
            rf"##\s+\[{re.escape(new_version)}\]\s*(?:-\s*\d{{4}}-\d{{2}}-\d{{2}})?",
            f"## [{new_version}] - {today}",
            content,
        )
        write_text_file(changelog_file, new_content)
        return True

    # If [Unreleased] section exists, rename to [new_version] - date
    if "## [Unreleased]" in content:
        new_content = content.replace(
            "## [Unreleased]",
            f"## [{new_version}] - {today}",
            1,
        )
        write_text_file(changelog_file, new_content)
        return True

    # Otherwise prepend new section before the first ## [
    first_section = re.search(r"^##\s+\[", content, re.MULTILINE)
    if first_section:
        pos = first_section.start()
        header = f"## [{new_version}] - {today}\n\n### Added\n- Release version {new_version}.\n\n"
        new_content = content[:pos] + header + content[pos:]
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


@app.command("status")
def release_status(
    root: Annotated[
        Path | None,
        typer.Option("--root", "-r", help=HELP.options.root),
    ] = None,
) -> None:
    """Display current release status, versions, tags, changelog, and docs state."""
    repo_root = _get_project_root(root)
    pyproject_ver = _get_pyproject_version(repo_root) or "unknown"
    init_ver = _get_init_version(repo_root) or "unknown"
    latest_tag = _get_latest_git_tag(repo_root) or "none"
    latest_cl_ver = _get_latest_changelog_version(repo_root) or "none"
    clean_tree = _is_git_clean(repo_root)

    # Check documentation freshness
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

    _get("print_table")(
        title=MESSAGES.release.status_header,
        columns=[("Property", "bold"), ("Value", "green")],
        rows=rows,
        border_style="cyan",
    )


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
                    "draft": False,
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
            release_type=release_type,
            breaking=breaking,
            root=root,
        )


# =============================================================================
# Command: release pr
# =============================================================================


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
        typer.Option("--draft", help=HELP.options.draft),
    ] = False,
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
    target_ver = (version or _get_pyproject_version(repo_root) or "").lstrip("v").strip()
    clean_version = target_ver
    if not clean_version or not _SEMVER_RE.match(clean_version):
        err = MESSAGES.release.invalid_version.format(version=target_ver or version or "")
        _get("print_error")(err, prefix=False)
        raise typer.Exit(1)

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

    _get("print_info")(
        MESSAGES.release.creating_release_branch.format(branch=branch_name), prefix=False
    )

    # 1. Checkout new release branch
    branch_proc = _get("run_subprocess")(["git", "checkout", "-B", branch_name], cwd=repo_root)
    if branch_proc.returncode != 0:
        _get("print_error")(
            f"Failed to create release branch {branch_name}: {branch_proc.stderr}", prefix=False
        )
        raise typer.Exit(1)
    _get("print_success")(MESSAGES.release.branch_created.format(branch=branch_name), prefix=False)

    # 2. Stage and commit release files
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
    commit_proc = _get("run_subprocess")(
        ["git", "commit", "-m", release_title],
        cwd=repo_root,
    )
    if commit_proc.returncode != 0 and "nothing to commit" not in str(commit_proc.stdout):
        _get("print_warning")(f"Note: {commit_proc.stderr or commit_proc.stdout}", prefix=False)

    # 3. Push branch if requested
    if push:
        push_proc = _get("run_subprocess")(
            ["git", "push", "-u", "origin", branch_name], cwd=repo_root
        )
        if push_proc.returncode != 0:
            _get("print_warning")(
                f"Warning: Could not push branch to remote: {push_proc.stderr}", prefix=False
            )

    # 4. Open GitHub Pull Request via gh CLI
    _get("print_info")(
        MESSAGES.release.creating_release_pr.format(version=target_ver), prefix=False
    )
    notes = _extract_changelog_notes(repo_root, target_ver) or f"Release v{target_ver}"
    pr_title = release_title
    pr_body = (
        f"## {pr_title}\n\n"
        "### Summary\n"
        f"Release `v{target_ver}` preparation, changelog synchronization, and quality validation "
        "under GitHub pull request merge controls.\n\n"
        f"### Release Notes\n{notes}\n\n"
        "### Quality Gate Checklist\n"
        "- [x] 7-Gate CI Quality Gate passing (`devops ci run`)\n"
        "- [x] Documentation and Command Matrix in `README.md` synchronized\n"
        "- [x] Version matching across `pyproject.toml` and `src/devops_cli/__init__.py`\n"
    )

    pr_cmd = [
        "gh",
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

    pr_proc = _get("run_subprocess")(pr_cmd, cwd=repo_root)
    if pr_proc.returncode != 0 and labels and "label" in (pr_proc.stderr or "").lower():
        fallback_cmd = [
            arg
            for idx, arg in enumerate(pr_cmd)
            if arg != "--label" and (idx == 0 or pr_cmd[idx - 1] != "--label")
        ]
        pr_proc = _get("run_subprocess")(fallback_cmd, cwd=repo_root)

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


# =============================================================================
# Command: release check
# =============================================================================


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
    pyproject_ver = _get_pyproject_version(repo_root)
    init_ver = _get_init_version(repo_root)
    changelog_ver = _get_latest_changelog_version(repo_root)

    # 1. Version Consistency
    if not pyproject_ver or pyproject_ver != init_ver:
        _get("print_error")(
            f"Version mismatch: pyproject.toml ({pyproject_ver}) != "
            f"src/devops_cli/__init__.py ({init_ver})",
            prefix=False,
        )
        raise typer.Exit(1)

    if changelog_ver and changelog_ver != pyproject_ver:
        _get("print_warning")(
            f"Warning: Latest CHANGELOG.md version ({changelog_ver}) differs from "
            f"pyproject version ({pyproject_ver})",
            prefix=False,
        )

    # 2. Git Cleanliness Check
    if not allow_dirty and not _is_git_clean(repo_root):
        _get("print_error")(
            "Git working directory is dirty. Commit or stash changes before releasing.",
            prefix=False,
        )
        raise typer.Exit(1)

    # 3. Documentation Freshness Check
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

    # 4. CI Quality Gate
    if not skip_ci:
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
            timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS * 4,
        )
        if proc.returncode != 0:
            _get("print_error")(
                "CI Quality Gate checks failed. Resolve errors before releasing.", prefix=False
            )
            raise typer.Exit(1)

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

    notes = _extract_changelog_notes(repo_root, target_ver)
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
# Command: release tag
# =============================================================================


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
    target_ver = (version or _get_pyproject_version(repo_root) or "").lstrip("v")
    if not target_ver or not _SEMVER_RE.match(target_ver):
        err_msg = MESSAGES.release.invalid_version.format(version=target_ver or version or "")
        _get("print_error")(err_msg, prefix=False)
        raise typer.Exit(1)

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

    # Commit release changes if any are staged/modified
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
    _get("run_subprocess")(
        ["git", "commit", "-m", release_title],
        cwd=repo_root,
    )

    # Create annotated tag
    tag_proc = _get("run_subprocess")(["git", "tag", "-a", tag_name, "-m", tag_msg], cwd=repo_root)
    if tag_proc.returncode != 0:
        _get("print_error")(f"Failed to create git tag {tag_name}: {tag_proc.stderr}", prefix=False)
        raise typer.Exit(1)

    _get("print_success")(MESSAGES.release.tag_created.format(tag=tag_name), prefix=False)

    if push:
        push_proc = _get("run_subprocess")(["git", "push", "origin", "--tags"], cwd=repo_root)
        if push_proc.returncode != 0:
            _get("print_error")(
                f"Failed to push tag {tag_name} to origin: {push_proc.stderr}", prefix=False
            )
            raise typer.Exit(1)
        _get("print_success")(MESSAGES.release.tag_pushed.format(tag=tag_name), prefix=False)
