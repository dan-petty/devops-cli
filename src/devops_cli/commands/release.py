"""Release management and release cycle orchestration subcommands."""

from __future__ import annotations

import importlib
import logging
import sys
import types
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import typer

import devops_cli.release.cut as _cut
from devops_cli.config.constants import (
    CONST_GIT_MAIN_BRANCH,
    CONST_PYPROJECT_FILENAME,
)
from devops_cli.config.defaults import (
    DEFAULT_RELEASE_LABEL,
    DEFAULT_RELEASE_TYPE,
    DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
)
from devops_cli.core.cli import new_typer
from devops_cli.dry_run import is_dry_run, render_dry_run_result
from devops_cli.exceptions import DevOpsCLIError
from devops_cli.lang import HELP, MESSAGES
from devops_cli.release.cut import (
    _LAZY_OBJECT_MAPPING,
    _RELEASE_NOTES_BUDGET,
    _SEMVER_RE,
    _apply_cut_modifications,
    _extract_changelog_notes,
    _extract_git_commit_notes,
    _format_release_title,
    _fragment_names,
    _FragmentCollection,
    _get_init_version,
    _get_latest_changelog_version,
    _get_latest_git_tag,
    _get_project_root,
    _get_pyproject_version,
    _is_git_clean,
    _notes_within,
    _plan_changelog_or_exit,
    _release_body_notes,
    _release_paths,
    _run_remote_git_or_exit,
    _validate_release_version,
    _write_version_changelog,
)
from devops_cli.release.cut import (
    cut_release as cut_release,
)

logger = logging.getLogger(__name__)
_ORIGINAL_CUT_ATTRS: dict[str, Any] = dict(_cut.__dict__)


def __getattr__(name: str) -> Any:
    if name in _LAZY_OBJECT_MAPPING:
        mod_path, obj_name = _LAZY_OBJECT_MAPPING[name]
        module = importlib.import_module(mod_path)
        return getattr(module, obj_name)
    if hasattr(_cut, name):
        return getattr(_cut, name)
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


app = new_typer(help=HELP.release.app, exit_on=DevOpsCLIError)


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


def _execute_release_prepare(
    repo_root: Path,
    clean_version: str,
    today: str,
    collection: _FragmentCollection | None,
    update_changelog: bool,
    sync_docs: bool,
) -> None:
    """Execute local version bumps, changelog updates, and docs generation."""
    _get("print_info")(
        MESSAGES.release.preparing_release.format(version=clean_version), prefix=False
    )
    _apply_cut_modifications(repo_root, clean_version, sync_docs=sync_docs)
    if update_changelog and _write_version_changelog(repo_root, clean_version, today, collection):
        _get("print_info")(
            MESSAGES.release.updated_changelog.format(version=clean_version, date=today),
            prefix=False,
        )
    _get("print_success")(f"Release preparation for v{clean_version} completed successfully.")


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
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Bump version across pyproject.toml and source, update changelog, and sync docs."""
    clean_version = version.lstrip("v").strip()
    if not _SEMVER_RE.match(clean_version):
        _get("print_error")(MESSAGES.release.invalid_version.format(version=version), prefix=False)
        raise typer.Exit(1)

    repo_root = _get_project_root(root)
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    collection = _plan_changelog_or_exit(repo_root, clean_version, today, update_changelog)

    if dry_run or is_dry_run():
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
                "changelog_fragments": _fragment_names(collection),
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
                    "release_type": release_type,
                    "breaking": breaking,
                    "title": _format_release_title(
                        clean_version, prefix=release_type, breaking=breaking
                    ),
                    "changelog_fragments": _fragment_names(collection),
                },
            )
        return

    if create_pr:
        cut_release(
            version=clean_version,
            draft=draft,
            release_type=release_type,
            breaking=breaking,
            sync_docs=sync_docs,
            is_prepare=True,
            repo_root=repo_root,
        )
        return

    _execute_release_prepare(
        repo_root=repo_root,
        clean_version=clean_version,
        today=today,
        collection=collection,
        update_changelog=update_changelog,
        sync_docs=sync_docs,
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
        typer.Option("--draft/--no-draft", help=HELP.options.draft),
    ] = True,
    labels: Annotated[
        str,
        typer.Option("--labels", "-l", help=HELP.options.labels),
    ] = DEFAULT_RELEASE_LABEL,
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
    """Create release cut branch, commit version bumps, and open a GitHub Release Pull Request."""
    cut_release(
        version=version,
        base=base,
        draft=draft,
        labels=labels,
        release_type=release_type,
        breaking=breaking,
        is_prepare=False,
        repo_root=root,
    )


# =============================================================================
# Command: release check
# =============================================================================


def _verify_release_versions(repo_root: Path) -> str:
    """Verify version consistency across pyproject.toml, __init__.py and CHANGELOG.md."""
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
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Print markdown release notes for a specified or current release version.

    Notes over GitHub's 125,000-character Release body limit are printed compact: each
    category and entry title without its sub-bullets, then a link to the version's section
    of CHANGELOG.md at its tag.
    """
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

    notes = _release_body_notes(repo_root, target_ver)
    if not notes:
        print_warning(MESSAGES.release.notes_not_found.format(version=target_ver), prefix=False)
        raise typer.Exit(1)

    if dry_run or is_dry_run():
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
# Command: release sync-notes
# =============================================================================


def _sync_one_release(repo: str, tag: str, repo_root: Path, dry_run: bool) -> str:
    """Bring one published release description back in line with the changelog."""
    from devops_cli.github.release_notes import (
        ReleaseBody,
        get_release_body,
        set_release_body,
    )

    published = get_release_body(repo, tag)
    if published is None:
        return MESSAGES.release.notes_unreadable.format(tag=tag)

    expected = _release_body_notes(repo_root, tag.lstrip("v"), repo)
    if not expected:
        return MESSAGES.release.notes_no_changelog.format(tag=tag)

    body = ReleaseBody(tag=tag, published=published, expected=expected)
    if not body.differs:
        return MESSAGES.release.notes_in_sync.format(tag=tag)

    stripped = " (removed GitHub's generated summary)" if body.carries_generated_notes else ""
    if dry_run or not set_release_body(repo, tag, expected):
        if dry_run:
            return MESSAGES.release.notes_republished.format(tag=tag, stripped=stripped)
        return MESSAGES.release.notes_republish_failed.format(tag=tag)
    return MESSAGES.release.notes_republished.format(tag=tag, stripped=stripped)


@app.command("sync-notes")
def release_sync_notes(
    version: Annotated[
        str | None,
        typer.Option("--version", "-v", help=HELP.options.version),
    ] = None,
    all_releases: Annotated[
        bool,
        typer.Option("--all", help=HELP.release.sync_notes_all),
    ] = False,
    repo: Annotated[
        str | None,
        typer.Option("--repo", "-R", help=HELP.pr.target_repo),
    ] = None,
    root: Annotated[
        Path | None,
        typer.Option("--root", "-r", help=HELP.options.root),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Republish GitHub release descriptions from CHANGELOG.md.

    A release body is written once at publish time. Nothing in the repository could change
    it afterwards, so a release published before the workflow disabled GitHub's generated
    summary keeps carrying it, and an edited changelog entry never reaches the release it
    describes. Notes over the Release body limit are sent in the compact form `release notes`
    prints.
    """
    from devops_cli.commands.gh import _resolve_repo
    from devops_cli.github.release_notes import list_published_releases

    repo_root = _get_project_root(root)
    target_repo = repo or _resolve_repo()
    if not target_repo or "/" not in target_repo:
        _get("print_error")("Cannot resolve target repository.")
        raise typer.Exit(1)

    active_dry_run = dry_run or is_dry_run()
    if all_releases:
        tags = (
            ["<all published releases>"] if active_dry_run else list_published_releases(target_repo)
        )
    else:
        target_ver = (version or _get_pyproject_version(repo_root) or "").lstrip("v")
        if not target_ver:
            _get("print_error")("Could not determine target release version.")
            raise typer.Exit(1)
        tags = [f"v{target_ver}"]

    if active_dry_run:
        render_dry_run_result(
            command="devops release sync-notes",
            action="republish_release_notes",
            details={"repo": target_repo, "releases": ", ".join(tags)},
        )
        return

    for tag in tags:
        _get("print_info")(_sync_one_release(target_repo, tag, repo_root, False))


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
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
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
    collection = _plan_changelog_or_exit(repo_root, target_ver, today, update)
    compiled_notes = (
        _extract_git_commit_notes(repo_root, target_ver)
        or f"### Changes in v{target_ver}\n\n* Release v{target_ver}"
    )

    if dry_run or is_dry_run():
        render_dry_run_result(
            command="devops release changelog",
            action="compile_release_changelog",
            target=target_ver,
            details={
                "version": target_ver,
                "update": update,
                "raw": raw,
                "from_tag": from_tag,
                "changelog_fragments": _fragment_names(collection),
            },
        )
        return

    if update:
        if _write_version_changelog(repo_root, target_ver, today, collection):
            print_success(
                MESSAGES.release.updated_changelog.format(version=target_ver, date=today),
                prefix=False,
            )
        return

    if raw:
        write_stdout(
            _notes_within(repo_root, target_ver, compiled_notes, _RELEASE_NOTES_BUDGET) + "\n"
        )
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
    _get("run_subprocess")(["git", "add", *_release_paths(repo_root)], cwd=repo_root)
    _get("run_subprocess")(
        ["git", "commit", "-m", release_title],
        cwd=repo_root,
    )


def _push_git_tag(repo_root: Path, tag_name: str, target_ver: str) -> None:
    """Push the annotated release tag, and no other, to origin and close release milestone."""
    _run_remote_git_or_exit(
        repo_root,
        f"Failed to push tag {tag_name} to origin",
        "push",
        "origin",
        f"refs/tags/{tag_name}",
    )
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
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Create release commit and annotated git tag."""
    repo_root = _get_project_root(root)
    target_ver = _validate_release_version(version, repo_root)

    tag_name = f"v{target_ver}"
    release_title = _format_release_title(target_ver, prefix=release_type, breaking=breaking)
    tag_msg = message or release_title

    if dry_run or is_dry_run():
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

    tag_proc = _get("run_subprocess")(["git", "tag", "-a", tag_name, "-m", tag_msg], cwd=repo_root)
    if tag_proc.returncode != 0:
        _get("print_error")(f"Failed to create git tag {tag_name}: {tag_proc.stderr}", prefix=False)
        raise typer.Exit(1)

    _get("print_success")(MESSAGES.release.tag_created.format(tag=tag_name), prefix=False)

    if push:
        _push_git_tag(repo_root, tag_name, target_ver)


def _close_release_milestone_safe(repo_root: Path, version: str) -> None:
    """Close the Release of `version` in the tagged repository, warning when GitHub can't."""
    from devops_cli.commands.gh import _resolve_repo
    from devops_cli.core.repo import get_repo_origin_name
    from devops_cli.exceptions import DevOpsCLIError
    from devops_cli.roadmap import store as roadmap_store

    target_repo = _resolve_repo(get_repo_origin_name(repo_root))
    try:
        closed = roadmap_store.get_roadmap_store(target_repo).close_release(version)
    except DevOpsCLIError as exc:
        _get("print_warning")(
            f"Note: Could not close milestone for v{version}: {exc}", prefix=False, safe=True
        )
        return
    _get("print_success")(f"Closed release milestone for {closed.title}.", prefix=False)


class _ReleaseModule(types.ModuleType):
    """Custom module forwarding patched attributes to `devops_cli.release.cut`."""

    def __setattr__(self, name: str, value: Any) -> None:
        super().__setattr__(name, value)
        setattr(_cut, name, value)

    def __delattr__(self, name: str) -> None:
        super().__delattr__(name)
        if name in _ORIGINAL_CUT_ATTRS:
            setattr(_cut, name, _ORIGINAL_CUT_ATTRS[name])
        else:
            _cut.__dict__.pop(name, None)


sys.modules[__name__].__class__ = _ReleaseModule
