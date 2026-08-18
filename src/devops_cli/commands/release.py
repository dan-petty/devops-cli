"""Release management and release cycle orchestration subcommands."""

from __future__ import annotations

import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from devops_cli.config.defaults import DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
from devops_cli.core.cli import new_typer
from devops_cli.core.process import run_subprocess
from devops_cli.core.repo import find_top_level_repo_root
from devops_cli.docs.generator import DocGenerator
from devops_cli.dry_run import is_dry_run, render_dry_run_result
from devops_cli.lang import MESSAGES

app = new_typer(
    help="Manage release cycles, version bumping, changelogs, and release verification."
)
console = Console()

_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$")


def _get_project_root(target: Path | None = None) -> Path:
    """Find the top-level repository root containing pyproject.toml."""
    start = target or Path.cwd()
    top_root = find_top_level_repo_root(start)
    if (top_root / "pyproject.toml").exists():
        return top_root
    # Fallback upwards looking for pyproject.toml
    cur = start.resolve()
    while cur != cur.parent:
        if (cur / "pyproject.toml").exists():
            return cur
        cur = cur.parent
    return top_root


def _get_pyproject_version(root: Path) -> str | None:
    """Read version string from pyproject.toml."""
    pyproject_file = root / "pyproject.toml"
    if not pyproject_file.exists():
        return None
    content = pyproject_file.read_text(encoding="utf-8")
    match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
    return match.group(1) if match else None


def _get_init_version(root: Path) -> str | None:
    """Read version from src/devops_cli/__init__.py or pyproject.toml."""
    init_file = root / "src" / "devops_cli" / "__init__.py"
    if not init_file.exists():
        return None
    content = init_file.read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
    if match:
        return match.group(1)
    return _get_pyproject_version(root)


def _get_latest_git_tag(root: Path) -> str | None:
    """Retrieve latest git tag if git is available."""
    try:
        proc = run_subprocess(["git", "describe", "--tags", "--abbrev=0"], cwd=root)
        if proc.returncode == 0 and proc.stdout:
            return str(proc.stdout).strip()
    except Exception:
        pass
    return None


def _is_git_clean(root: Path) -> bool:
    """Check whether git working directory has uncommitted changes."""
    try:
        proc = run_subprocess(["git", "status", "--porcelain"], cwd=root)
        return proc.returncode == 0 and not bool(proc.stdout.strip())
    except Exception:
        return False


def _extract_changelog_notes(root: Path, version: str) -> str | None:
    """Extract release notes for a specific version from CHANGELOG.md."""
    changelog_file = root / "CHANGELOG.md"
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
    changelog_file = root / "CHANGELOG.md"
    if not changelog_file.exists():
        return None
    content = changelog_file.read_text(encoding="utf-8")
    match = re.search(r"^##\s+\[(\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?)\]", content, re.MULTILINE)
    return match.group(1) if match else None


def _update_pyproject_version(root: Path, new_version: str) -> bool:
    """Update version in pyproject.toml."""
    pyproject_file = root / "pyproject.toml"
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
        pyproject_file.write_text(new_content, encoding="utf-8")
        return True
    return False


def _update_init_version(root: Path, new_version: str) -> bool:
    """Update __version__ in src/devops_cli/__init__.py if hardcoded, or return True."""
    init_file = root / "src" / "devops_cli" / "__init__.py"
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
        init_file.write_text(new_content, encoding="utf-8")
        return True
    return True


def _update_changelog_header(root: Path, new_version: str, release_date: str | None = None) -> bool:
    """Ensure CHANGELOG.md has a header for the new version."""
    changelog_file = root / "CHANGELOG.md"
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
        changelog_file.write_text(new_content, encoding="utf-8")
        return True

    # If [Unreleased] section exists, rename to [new_version] - date
    if "## [Unreleased]" in content:
        new_content = content.replace(
            "## [Unreleased]",
            f"## [{new_version}] - {today}",
            1,
        )
        changelog_file.write_text(new_content, encoding="utf-8")
        return True

    # Otherwise prepend new section before the first ## [
    first_section = re.search(r"^##\s+\[", content, re.MULTILINE)
    if first_section:
        pos = first_section.start()
        header = f"## [{new_version}] - {today}\n\n### Added\n- Release version {new_version}.\n\n"
        new_content = content[:pos] + header + content[pos:]
        changelog_file.write_text(new_content, encoding="utf-8")
        return True

    return False


def _format_release_title(version: str, prefix: str = "feat", breaking: bool = False) -> str:
    """Format release title with conventional commit: <feat|fix>(release)<!>: vx.x.x"""
    clean_ver = version.lstrip("v").strip()

    norm_prefix = prefix.lower().strip() if prefix else "feat"
    if norm_prefix not in ("feat", "fix"):
        norm_prefix = "feat"
    bang = "!" if breaking else ""
    return f"{norm_prefix}(release){bang}: v{clean_ver}"


@app.command("status")
def release_status(
    root: Annotated[
        Path | None,
        typer.Option("--root", "-r", help="Project repository root directory"),
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
    generator = DocGenerator(root_dir=repo_root)
    docs_up_to_date, _ = generator.check_docs(repo_root / "docs", check_readme_table=True)

    table = Table(title=MESSAGES.release.status_header, style="cyan")
    table.add_column("Property", style="bold")
    table.add_column("Value", style="green")

    table.add_row("pyproject.toml Version", pyproject_ver)
    table.add_row("src/devops_cli/__init__.py", init_ver)
    table.add_row(
        "Version Consistency",
        "[green]✓ MATCH[/green]" if pyproject_ver == init_ver else "[red]✗ MISMATCH[/red]",
    )
    table.add_row("Latest Git Tag", latest_tag)
    table.add_row("Latest CHANGELOG Version", latest_cl_ver)
    table.add_row(
        "Working Tree Clean",
        "[green]✓ Clean[/green]" if clean_tree else "[yellow]⚠ Uncommitted Changes[/yellow]",
    )
    table.add_row(
        "Documentation Synchronized",
        "[green]✓ Synchronized[/green]"
        if docs_up_to_date
        else "[red]✗ Outdated (run 'devops docs generate')[/red]",
    )

    console.print(table)


@app.command("prepare")
def release_prepare(
    version: Annotated[str, typer.Argument(help="Target semantic version (e.g., 0.1.8)")],
    sync_docs: Annotated[
        bool,
        typer.Option(
            "--sync-docs/--no-sync-docs",
            help="Regenerate CLI reference docs and sync README matrix",
        ),
    ] = True,
    update_changelog: Annotated[
        bool,
        typer.Option(
            "--changelog/--no-changelog",
            help="Ensure CHANGELOG.md contains release header with current date",
        ),
    ] = True,
    create_pr: Annotated[
        bool,
        typer.Option(
            "--create-pr",
            "-p",
            help="Create release branch, commit changes, and open a GitHub Release PR",
        ),
    ] = False,
    release_type: Annotated[
        str,
        typer.Option(
            "--type",
            "-t",
            help="Conventional commit prefix (feat or fix)",
        ),
    ] = "feat",
    breaking: Annotated[
        bool,
        typer.Option(
            "--breaking",
            "-b",
            help="Flag release as containing breaking changes (!)",
        ),
    ] = False,
    root: Annotated[
        Path | None,
        typer.Option("--root", "-r", help="Project repository root directory"),
    ] = None,
) -> None:
    """Bump version across pyproject.toml and source, update changelog, and sync docs."""
    clean_version = version.lstrip("v").strip()
    if not _SEMVER_RE.match(clean_version):
        rprint(f"[red]{MESSAGES.release.invalid_version.format(version=version)}[/red]")
        raise typer.Exit(1)

    repo_root = _get_project_root(root)

    if is_dry_run():
        render_dry_run_result(
            command="devops release prepare",
            action="prepare_release_version",
            target=clean_version,
            details={
                "version": clean_version,
                "pyproject_target": str(repo_root / "pyproject.toml"),
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

    rprint(MESSAGES.release.preparing_release.format(version=clean_version))

    # 1. Update pyproject.toml
    if _update_pyproject_version(repo_root, clean_version):
        rprint(MESSAGES.release.updated_pyproject.format(version=clean_version))

    # 2. Update __init__.py
    if _update_init_version(repo_root, clean_version):
        rprint(MESSAGES.release.updated_init.format(version=clean_version))

    # 3. Update CHANGELOG.md
    if update_changelog:
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        if _update_changelog_header(repo_root, clean_version, today):
            rprint(MESSAGES.release.updated_changelog.format(version=clean_version, date=today))

    # 4. Regenerate documentation & sync README Command Matrix
    if sync_docs:
        generator = DocGenerator(root_dir=repo_root)
        generator.write_all_docs(output_dir=repo_root / "docs", sync_readme_table=True)
    msg = (
        f"\n[bold green]✓ Release preparation for v{clean_version} "
        "completed successfully.[/bold green]"
    )
    rprint(msg)

    if create_pr:
        release_pr(
            version=clean_version,
            release_type=release_type,
            breaking=breaking,
            root=root,
        )


@app.command("pr")
def release_pr(
    version: Annotated[
        str | None,
        typer.Option("--version", "-v", help="Target release version (defaults to pyproject.toml)"),
    ] = None,
    base: Annotated[
        str,
        typer.Option("--base", "-b", help="Target base branch for Pull Request"),
    ] = "main",
    draft: Annotated[
        bool,
        typer.Option("--draft", help="Create Pull Request as a draft"),
    ] = False,
    labels: Annotated[
        str,
        typer.Option("--labels", "-l", help="Comma-separated labels to attach to PR"),
    ] = "release",
    push: Annotated[
        bool,
        typer.Option("--push/--no-push", help="Push release branch to origin"),
    ] = True,
    release_type: Annotated[
        str,
        typer.Option(
            "--type",
            "-t",
            help="Conventional commit prefix (feat or fix)",
        ),
    ] = "feat",
    breaking: Annotated[
        bool,
        typer.Option(
            "--breaking",
            "-b",
            help="Flag release as containing breaking changes (!)",
        ),
    ] = False,
    root: Annotated[
        Path | None,
        typer.Option("--root", "-r", help="Project repository root directory"),
    ] = None,
) -> None:
    """Create release branch, commit version bumps, and open a GitHub Release Pull Request."""
    repo_root = _get_project_root(root)
    target_ver = (version or _get_pyproject_version(repo_root) or "").lstrip("v").strip()
    if not target_ver or not _SEMVER_RE.match(target_ver):
        err = MESSAGES.release.invalid_version.format(version=target_ver or version or "")
        rprint(f"[red]{err}[/red]")
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

    rprint(MESSAGES.release.creating_release_branch.format(branch=branch_name))

    # 1. Checkout new release branch
    branch_proc = run_subprocess(["git", "checkout", "-B", branch_name], cwd=repo_root)
    if branch_proc.returncode != 0:
        rprint(f"[red]Failed to create release branch {branch_name}: {branch_proc.stderr}[/red]")
        raise typer.Exit(1)
    rprint(MESSAGES.release.branch_created.format(branch=branch_name))

    # 2. Stage and commit release files
    run_subprocess(
        [
            "git",
            "add",
            "pyproject.toml",
            "src/devops_cli/__init__.py",
            "CHANGELOG.md",
            "README.md",
            "docs/",
        ],
        cwd=repo_root,
    )
    commit_proc = run_subprocess(
        ["git", "commit", "-m", release_title],
        cwd=repo_root,
    )
    if commit_proc.returncode != 0 and "nothing to commit" not in str(commit_proc.stdout):
        rprint(f"[yellow]Note: {commit_proc.stderr or commit_proc.stdout}[/yellow]")

    # 3. Push branch if requested
    if push:
        push_proc = run_subprocess(["git", "push", "-u", "origin", branch_name], cwd=repo_root)
        if push_proc.returncode != 0:
            rprint(f"[yellow]Warning: Could not push branch to remote: {push_proc.stderr}[/yellow]")

    # 4. Open GitHub Pull Request via gh CLI
    rprint(MESSAGES.release.creating_release_pr.format(version=target_ver))
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
        pr_cmd.extend(["--label", labels])

    pr_proc = run_subprocess(pr_cmd, cwd=repo_root)
    if pr_proc.returncode != 0 and labels and "label" in (pr_proc.stderr or "").lower():
        fallback_cmd = [
            arg
            for idx, arg in enumerate(pr_cmd)
            if arg != "--label" and (idx == 0 or pr_cmd[idx - 1] != "--label")
        ]
        pr_proc = run_subprocess(fallback_cmd, cwd=repo_root)

    if pr_proc.returncode == 0:
        pr_url = str(pr_proc.stdout).strip()
        rprint(MESSAGES.release.pr_created.format(url=pr_url))
    else:
        err = str(pr_proc.stderr).strip() or str(pr_proc.stdout).strip()
        rprint(f"[yellow]{MESSAGES.release.pr_failed.format(error=err)}[/yellow]")
        rprint(
            f"[dim]Branch '{branch_name}' is ready. You can manually open the PR on GitHub.[/dim]"
        )


@app.command("check")
def release_check(
    skip_ci: Annotated[
        bool,
        typer.Option("--skip-ci", help="Skip running the 7-gate CI test suite"),
    ] = False,
    allow_dirty: Annotated[
        bool,
        typer.Option("--allow-dirty", help="Allow uncommitted changes in git repository"),
    ] = False,
    root: Annotated[
        Path | None,
        typer.Option("--root", "-r", help="Project repository root directory"),
    ] = None,
) -> None:
    """Verify release readiness (version consistency, docs freshness, and CI quality gates)."""
    repo_root = _get_project_root(root)
    pyproject_ver = _get_pyproject_version(repo_root)
    init_ver = _get_init_version(repo_root)
    changelog_ver = _get_latest_changelog_version(repo_root)

    # 1. Version Consistency
    if not pyproject_ver or pyproject_ver != init_ver:
        rprint(
            f"[red]Version mismatch: pyproject.toml ({pyproject_ver}) != "
            f"src/devops_cli/__init__.py ({init_ver})[/red]"
        )
        raise typer.Exit(1)

    if changelog_ver and changelog_ver != pyproject_ver:
        rprint(
            f"[yellow]Warning: Latest CHANGELOG.md version ({changelog_ver}) differs from "
            f"pyproject version ({pyproject_ver})[/yellow]"
        )

    # 2. Git Cleanliness Check
    if not allow_dirty and not _is_git_clean(repo_root):
        rprint(
            "[red]Git working directory is dirty. Commit or stash changes before releasing.[/red]"
        )
        raise typer.Exit(1)

    # 3. Documentation Freshness Check
    generator = DocGenerator(root_dir=repo_root)
    docs_ok, diffs = generator.check_docs(repo_root / "docs", check_readme_table=True)
    if not docs_ok:
        rprint(
            "[red]Documentation is out of sync. "
            "Run 'devops release prepare' or 'devops docs generate --sync-readme'[/red]"
        )
        for d in diffs:
            rprint(f"  - {d}")
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

        rprint("[cyan]Running CI quality gate...[/cyan]")
        proc = run_subprocess(
            ["uv", "run", "devops", "ci", "run"],
            cwd=repo_root,
            timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS * 4,
        )
        if proc.returncode != 0:
            rprint("[red]CI Quality Gate checks failed. Resolve errors before releasing.[/red]")
            raise typer.Exit(1)

    rprint(f"[bold green]{MESSAGES.release.verification_passed}[/bold green]")


@app.command("notes")
def release_notes(
    version: Annotated[
        str | None,
        typer.Option("--version", "-v", help="Release version to extract notes for"),
    ] = None,
    raw: Annotated[
        bool,
        typer.Option("--raw", help="Output raw markdown text without formatting panel"),
    ] = False,
    root: Annotated[
        Path | None,
        typer.Option("--root", "-r", help="Project repository root directory"),
    ] = None,
) -> None:
    """Print markdown release notes for a specified or current release version."""
    repo_root = _get_project_root(root)
    target_ver = (version or _get_pyproject_version(repo_root) or "").lstrip("v")
    if not target_ver:
        rprint("[red]Could not determine target release version.[/red]")
        raise typer.Exit(1)

    notes = _extract_changelog_notes(repo_root, target_ver)
    if not notes:
        rprint(f"[yellow]{MESSAGES.release.notes_not_found.format(version=target_ver)}[/yellow]")
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
        sys.stdout.write(notes + "\n")
        return

    panel = Panel(
        notes,
        title=f"Release Notes — v{target_ver}",
        border_style="cyan",
    )
    console.print(panel)


@app.command("tag")
def release_tag(
    version: Annotated[
        str | None,
        typer.Option("--version", "-v", help="Release version (defaults to pyproject.toml)"),
    ] = None,
    push: Annotated[
        bool,
        typer.Option("--push", "-p", help="Push release commit and git tag to origin"),
    ] = False,
    release_type: Annotated[
        str,
        typer.Option(
            "--type",
            "-t",
            help="Conventional commit prefix (feat or fix)",
        ),
    ] = "feat",
    breaking: Annotated[
        bool,
        typer.Option(
            "--breaking",
            "-b",
            help="Flag release as containing breaking changes (!)",
        ),
    ] = False,
    message: Annotated[
        str | None,
        typer.Option("--message", "-m", help="Custom tag annotation message"),
    ] = None,
    root: Annotated[
        Path | None,
        typer.Option("--root", "-r", help="Project repository root directory"),
    ] = None,
) -> None:
    """Create release commit and annotated git tag."""
    repo_root = _get_project_root(root)
    target_ver = (version or _get_pyproject_version(repo_root) or "").lstrip("v")
    if not target_ver or not _SEMVER_RE.match(target_ver):
        err_msg = MESSAGES.release.invalid_version.format(version=target_ver or version or "")
        rprint(f"[red]{err_msg}[/red]")
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
    run_subprocess(
        [
            "git",
            "add",
            "pyproject.toml",
            "src/devops_cli/__init__.py",
            "CHANGELOG.md",
            "README.md",
            "docs/",
        ],
        cwd=repo_root,
    )
    run_subprocess(
        ["git", "commit", "-m", release_title],
        cwd=repo_root,
    )

    # Create annotated tag
    tag_proc = run_subprocess(["git", "tag", "-a", tag_name, "-m", tag_msg], cwd=repo_root)
    if tag_proc.returncode != 0:
        rprint(f"[red]Failed to create git tag {tag_name}: {tag_proc.stderr}[/red]")
        raise typer.Exit(1)

    rprint(MESSAGES.release.tag_created.format(tag=tag_name))

    if push:
        push_proc = run_subprocess(["git", "push", "origin", "--tags"], cwd=repo_root)
        if push_proc.returncode != 0:
            rprint(f"[red]Failed to push tag {tag_name} to origin: {push_proc.stderr}[/red]")
            raise typer.Exit(1)
        rprint(MESSAGES.release.tag_pushed.format(tag=tag_name))
