"""Release cut domain logic, version/changelog helpers, and PR preparation (#848)."""

from __future__ import annotations

import importlib
import json
import logging
import os
import re
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NamedTuple, NoReturn

import typer

from devops_cli.config.constants import (
    CONST_APP_NAME,
    CONST_CHANGELOG_FILENAME,
    CONST_CHANGELOG_FRAGMENTS_DIR,
    CONST_CONVENTIONAL_COMMIT_CATEGORIES,
    CONST_CONVENTIONAL_COMMIT_CATEGORY_ORDER,
    CONST_DOCS_DIR_NAME,
    CONST_GH_CLI,
    CONST_GIT_CLI,
    CONST_GIT_MAIN_BRANCH,
    CONST_GIT_NO_TERMINAL_PROMPT_ENV,
    CONST_GITHUB_HTTPS_PREFIX,
    CONST_GITHUB_PULL_REQUEST_BODY_MAX_CHARS,
    CONST_GITHUB_RELEASE_BODY_MAX_CHARS,
    CONST_INIT_PY_PATH,
    CONST_PYPROJECT_FILENAME,
    CONST_README_FILENAME,
    CONST_UV_LOCK_FILENAME,
)
from devops_cli.config.defaults import (
    DEFAULT_RELEASE_LABEL,
    DEFAULT_RELEASE_TYPE,
)
from devops_cli.dry_run import is_dry_run, render_dry_run_result
from devops_cli.exceptions import (
    DevOpsCLIError,
    GitOperationError,
    ReleaseBranchMissingError,
    ReleasePRCreationError,
    ReleasePushError,
    ReleasePushRefusedError,
    ReleaseRemoteFetchError,
    ReleaseWorkingTreeDirtyError,
)
from devops_cli.exceptions.validation import ValidationError
from devops_cli.lang import ERRORS, MESSAGES
from devops_cli.release.changelog_fragments import (
    changelog_heading_anchor,
    collect_changelog_fragments,
    find_changelog_section,
    read_changelog_fragments,
)
from devops_cli.release.notes_compaction import fit_release_notes

logger = logging.getLogger(__name__)

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
    "check_argocd_gate": ("devops_cli.k8s.argocd_gate", "check_argocd_gate"),
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


_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$")


def _get_project_root(target: Path | None = None) -> Path:
    """Find the repository or worktree root containing pyproject.toml."""
    from devops_cli.core.repo import find_worktree_root

    return find_worktree_root(target)


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


def _get_project_name(root: Path) -> str:
    """Read project name from pyproject.toml, defaulting to CONST_APP_NAME."""
    pyproject_file = _resolve_safe_project_path(root, CONST_PYPROJECT_FILENAME)
    if not pyproject_file.exists():
        return CONST_APP_NAME
    content = pyproject_file.read_text(encoding="utf-8")
    match = re.search(r'name\s*=\s*["\']([^"\']+)["\']', content)
    return match.group(1) if match else CONST_APP_NAME


def _get_init_version(root: Path) -> str | None:
    """Read version from src/devops_cli/__init__.py or pyproject.toml."""
    init_file = _resolve_safe_project_path(root, CONST_INIT_PY_PATH)
    if not init_file.exists():
        return None
    content = init_file.read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
    if match:
        return match.group(1)
    if "__version__" in content:
        return _get_pyproject_version(root)
    return None


def _get_latest_git_tag(root: Path) -> str | None:
    """Retrieve latest git tag if git is available."""
    from devops_cli.git.operations import get_latest_git_tag

    return get_latest_git_tag(root)


def _is_git_clean(root: Path) -> bool:
    """Check whether git working directory has uncommitted changes."""
    try:
        proc = _get("run_subprocess")(
            ["git", "status", "--porcelain"],
            cwd=root,
            capture_output=True,
            check=False,
            quiet=True,
        )
        return proc.returncode == 0 and not bool(proc.stdout.strip())
    except OSError, RuntimeError, ValueError, DevOpsCLIError:
        return False


def _extract_changelog_notes(root: Path, version: str) -> str | None:
    """Extract release notes for a specific version from CHANGELOG.md."""
    changelog_file = _resolve_safe_project_path(root, CONST_CHANGELOG_FILENAME)
    if not changelog_file.exists():
        return None
    section = find_changelog_section(
        changelog_file.read_text(encoding="utf-8"), version.lstrip("v")
    )
    return section.body.strip() if section else None


def _full_notes_pointer(root: Path, version: str, repo: str | None = None) -> str:
    """Where a version's full notes are: its CHANGELOG.md section at the version's tag.

    It is a link when the repository is known, from `repo`, the git origin or the
    `GITHUB_REPOSITORY` GitHub Actions sets; otherwise it names the file and the tag.
    """
    from devops_cli.core.repo import get_repo_origin_name

    repo = repo or get_repo_origin_name(root) or os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        return MESSAGES.release.notes_full_notes_unlinked.format(version=version)
    changelog_file = _resolve_safe_project_path(root, CONST_CHANGELOG_FILENAME)
    changelog = changelog_file.read_text(encoding="utf-8") if changelog_file.exists() else ""
    section = find_changelog_section(changelog, version)
    anchor = f"#{changelog_heading_anchor(section.heading)}" if section else ""
    url = f"{CONST_GITHUB_HTTPS_PREFIX}{repo}/blob/v{version}/{CONST_CHANGELOG_FILENAME}{anchor}"
    return MESSAGES.release.notes_full_notes_linked.format(version=version, url=url)


def _notes_within(
    root: Path, version: str, notes: str, budget: int, repo: str | None = None
) -> str:
    """`notes` if they fit in `budget` characters, else their compact form (#1097).

    Notes that fit need no pointer to the full notes, so none is built for them.
    """
    if len(notes) <= budget:
        return notes
    return fit_release_notes(notes, budget, _full_notes_pointer(root, version, repo))


# A Release body is the notes and the newline `--raw` ends them with.
_RELEASE_NOTES_BUDGET = CONST_GITHUB_RELEASE_BODY_MAX_CHARS - len("\n")


def _release_body_notes(root: Path, version: str, repo: str | None = None) -> str | None:
    """The notes a version's GitHub Release carries, within GitHub's Release body limit."""
    notes = _resolve_release_notes(root, version)
    return _notes_within(root, version, notes, _RELEASE_NOTES_BUDGET, repo) if notes else None


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


_TRAILING_REFERENCES_RE = re.compile(r"(?:\s*\(#\d+\))+\s*$")


def _deduplication_key(line: str) -> str:
    """Reduce a subject to what identifies the change rather than how it was merged."""
    return _TRAILING_REFERENCES_RE.sub("", line).strip().lower()


def _is_conventional_subject(line: str) -> bool:
    """Report whether a line is a conventional commit subject rather than prose."""
    match = _CONVENTIONAL_RE.match(line)
    return bool(match and match.group(1).lower() in CONST_CONVENTIONAL_COMMIT_CATEGORIES)


def _extract_raw_commit_lines(raw_log: str) -> list[str]:
    """Extract changelog-worthy subjects from git log output."""
    raw_lines = [
        line.strip().lstrip("*- ").strip() for line in raw_log.splitlines() if line.strip()
    ]
    candidates = [
        line for line in raw_lines if len(line) > 4 and not _RELEASE_COMMIT_RE.match(line)
    ]
    conventional = [line for line in candidates if _is_conventional_subject(line)]
    selected = conventional or candidates

    seen: set[str] = set()
    items: list[str] = []
    for line in selected:
        key = _deduplication_key(line)
        if key not in seen:
            seen.add(key)
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
    if "__version__" not in content:
        return False
    match = re.search(r'(__version__\s*=\s*["\'])[^"\']+(["\'])', content)
    if not match:
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


def _update_uv_lock_version(root: Path, new_version: str) -> bool:
    """Update the project package version in uv.lock if present."""
    from devops_cli.output import write_text_file

    uv_lock_file = _resolve_safe_project_path(root, CONST_UV_LOCK_FILENAME)
    if not uv_lock_file.exists():
        return False
    name = _get_project_name(root)
    content = uv_lock_file.read_text(encoding="utf-8")
    pattern = (
        r'(\[\[package\]\]\s*\n\s*name\s*=\s*["\']'
        + re.escape(name)
        + r'["\']\s*\n\s*version\s*=\s*["\'])[^"\']+(["\'])'
    )
    new_content, count = re.subn(pattern, rf"\g<1>{new_version}\g<2>", content, count=1)
    if count > 0:
        write_text_file(uv_lock_file, new_content)
        return True
    return False


def _existing_changelog_entries(notes: str | None) -> list[str]:
    """Read the bullet entries already written under a version heading."""
    if not notes:
        return []
    return [
        line.strip()[2:].strip() for line in notes.splitlines() if line.strip().startswith("- ")
    ]


def _merge_changelog_entries(existing: list[str], compiled: list[str]) -> list[str]:
    """Combine entries already present with newly compiled ones, without repeating any."""
    merged = list(existing)
    seen = {_deduplication_key(entry) for entry in existing}
    for entry in compiled:
        key = _deduplication_key(entry)
        if key not in seen:
            seen.add(key)
            merged.append(entry)
    return merged


def _build_changelog_section(
    root: Path, new_version: str, today: str, existing_notes: str | None = None
) -> str:
    """Build a changelog section, folding in anything already written under the heading."""
    compiled_notes = _extract_git_commit_notes(root, new_version)
    compiled = (
        _extract_raw_commit_lines(re.sub(r"^###[^\n]*\n", "", compiled_notes, flags=re.MULTILINE))
        if compiled_notes
        else []
    )
    merged = _merge_changelog_entries(_existing_changelog_entries(existing_notes), compiled)
    if merged:
        body = re.sub(
            r"^###\s+Changes in v[^\n]+\n*", "", _format_categorized_notes(merged, new_version)
        ).strip()
        if body:
            return f"## [{new_version}] - {today}\n\n{body}\n\n"
    return f"## [{new_version}] - {today}\n\n### Added\n- Release version {new_version}.\n\n"


def _update_changelog_header(root: Path, new_version: str, release_date: str | None = None) -> bool:
    """Ensure CHANGELOG.md has a header for the new version."""
    from devops_cli.output import write_text_file

    changelog_file = _resolve_safe_project_path(root, CONST_CHANGELOG_FILENAME)
    if not changelog_file.exists():
        return False
    today = release_date or datetime.now(UTC).strftime("%Y-%m-%d")
    content = changelog_file.read_text(encoding="utf-8")

    if f"## [{new_version}]" in content:
        current_notes = _extract_changelog_notes(root, new_version)
        section = _build_changelog_section(root, new_version, today, existing_notes=current_notes)
        pattern = rf"##\s+\[{re.escape(new_version)}\][^\n]*\n(?:(?!^##\s+\[).*\n)*"
        new_content = re.sub(pattern, lambda _: section, content, count=1, flags=re.MULTILINE)
        write_text_file(changelog_file, new_content)
        return True

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

    first_section = re.search(r"^##\s+\[", content, re.MULTILINE)
    if first_section:
        pos = first_section.start()
        section = _build_changelog_section(root, new_version, today)
        new_content = content[:pos] + section + content[pos:]
        write_text_file(changelog_file, new_content)
        return True

    return False


class _FragmentCollection(NamedTuple):
    """The CHANGELOG.md text a cut writes, and the fragments it deletes once that is written."""

    changelog_file: Path
    text: str
    fragments: tuple[Path, ...]


def _plan_fragment_collection(root: Path, version: str, today: str) -> _FragmentCollection | None:
    """Read every fragment and the CHANGELOG.md they make, raising before anything is written."""
    fragments = read_changelog_fragments(
        _resolve_safe_project_path(root, CONST_CHANGELOG_FRAGMENTS_DIR)
    )
    changelog_file = _resolve_safe_project_path(root, CONST_CHANGELOG_FILENAME)
    if not fragments or not changelog_file.exists():
        return None
    content = changelog_file.read_text(encoding="utf-8")
    text = collect_changelog_fragments(content, version, today, fragments)
    if text is None:
        return None
    return _FragmentCollection(changelog_file, text, tuple(fragment.path for fragment in fragments))


def _plan_changelog_or_exit(
    root: Path, version: str, today: str, update_changelog: bool
) -> _FragmentCollection | None:
    """Plan the fragment collection when the changelog is to be written, exiting 1 on a refusal."""
    if not update_changelog:
        return None
    try:
        return _plan_fragment_collection(root, version, today)
    except ValidationError as exc:
        _get("print_error")(str(exc), prefix=False, safe=True)
        raise typer.Exit(1) from exc


def _fragment_names(collection: _FragmentCollection | None) -> list[str]:
    """The fragments a run collects, as their repository paths."""
    paths = collection.fragments if collection is not None else ()
    return [f"{CONST_CHANGELOG_FRAGMENTS_DIR}/{path.name}" for path in paths]


def _write_version_changelog(
    root: Path, version: str, today: str, collection: _FragmentCollection | None
) -> bool:
    """Write the version's CHANGELOG.md section, from the fragments when there are any."""
    if collection is None:
        return _update_changelog_header(root, version, today)
    from devops_cli.output import write_text_file

    write_text_file(collection.changelog_file, collection.text)
    for fragment in collection.fragments:
        fragment.unlink()
    return True


def _release_paths(root: Path) -> list[str]:
    """The paths a release commit stages."""
    paths = [
        CONST_PYPROJECT_FILENAME,
        str(CONST_INIT_PY_PATH),
        CONST_CHANGELOG_FILENAME,
        CONST_README_FILENAME,
        f"{CONST_DOCS_DIR_NAME}/",
    ]
    if (root / CONST_UV_LOCK_FILENAME).is_file():
        paths.append(CONST_UV_LOCK_FILENAME)
    if (root / CONST_CHANGELOG_FRAGMENTS_DIR).is_dir():
        paths.append(f"{CONST_CHANGELOG_FRAGMENTS_DIR}/")
    return paths


def _present_fragment_names(root: Path) -> list[str]:
    """The fragments present in changelog.d/, as their repository paths."""
    frag_dir = _resolve_safe_project_path(root, CONST_CHANGELOG_FRAGMENTS_DIR)
    fragments = read_changelog_fragments(frag_dir)
    return [f"{CONST_CHANGELOG_FRAGMENTS_DIR}/{frag.path.name}" for frag in fragments]


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


def _validate_release_version(version: str | None, repo_root: Path) -> str:
    """Validate and normalize release semantic version string."""
    if version and version.strip():
        target_ver = version.lstrip("v").strip()
    else:
        branch_proc = _get("run_subprocess")(
            ["git", "branch", "--show-current"],
            cwd=repo_root,
            capture_output=True,
            check=False,
            quiet=True,
        )
        curr_branch = (
            branch_proc.stdout.strip() if branch_proc.returncode == 0 and branch_proc.stdout else ""
        )
        match = re.match(r"^release/v(.+)$", curr_branch)
        if match:
            target_ver = match.group(1).lstrip("v").strip()
        else:
            target_ver = (_get_pyproject_version(repo_root) or "").lstrip("v").strip()

    if not target_ver or not _SEMVER_RE.match(target_ver):
        err = MESSAGES.release.invalid_version.format(version=target_ver or version or "")
        _get("print_error")(err, prefix=False)
        raise typer.Exit(1)
    return target_ver


def _verify_clean_tree(root: Path) -> None:
    """Ensure working directory has no uncommitted changes before cutting release."""
    if not _is_git_clean(root):
        raise ReleaseWorkingTreeDirtyError(
            "Working directory has uncommitted changes. Stash or commit them before cutting a release."
        )


def _is_ruleset_refusal(raw_output: str) -> bool:
    """Return True if git output indicates push refusal by a repository ruleset."""
    text = raw_output.lower()
    return "gh013" in text or "repository rule violations found" in text


def _raise_remote_git_failure(failure: str, reason: str, git_args: tuple[str, ...]) -> NoReturn:
    """Raise the appropriate typed GitOperationError subclass for a failed remote git command."""
    from devops_cli.security.sanitizer import mask_secrets

    clean_reason = mask_secrets(reason)
    if "fetch" in git_args:
        raise ReleaseRemoteFetchError(f"{failure}: {clean_reason}")
    if "push" in git_args:
        if _is_ruleset_refusal(reason):
            msg = (
                f"{failure}: push refused by repository ruleset (GH013). "
                "Direct pushes to release branches require Write role bypass on the "
                "release ruleset (ruleset 23059172 in Settings → Rules → Rulesets). "
                f"Git output: {clean_reason}"
            )
            raise ReleasePushRefusedError(msg, details={"git_output": clean_reason})
        raise ReleasePushError(f"{failure}: {clean_reason}", details={"git_output": clean_reason})
    raise GitOperationError(f"{failure}: {clean_reason}")


def _run_remote_git_or_exit(root: Path, failure: str, *git_args: str) -> None:
    """Run a git command that reaches origin in the person's own environment, or raise typed error (#1124, #1280)."""
    proc = _get("run_subprocess")(
        [CONST_GIT_CLI, *git_args],
        cwd=root,
        capture_output=True,
        check=False,
        isolate_env=False,
        env=CONST_GIT_NO_TERMINAL_PROMPT_ENV,
    )
    if proc.returncode != 0:
        reason = str(proc.stderr).strip() or str(proc.stdout).strip()
        _raise_remote_git_failure(failure, reason, git_args)


def _fetch_remote_release_tip(root: Path, release_branch: str) -> None:
    """Fetch remote release branch from origin and verify its existence."""
    remote_ref = f"origin/{release_branch}"
    _run_remote_git_or_exit(
        root, f"Failed to fetch {remote_ref}", "fetch", "origin", release_branch
    )
    rev_proc = _get("run_subprocess")(
        ["git", "rev-parse", "--verify", "--quiet", remote_ref],
        cwd=root,
        capture_output=True,
        check=False,
        quiet=True,
    )
    if rev_proc.returncode != 0:
        raise ReleaseBranchMissingError(
            f"Remote release branch '{remote_ref}' does not exist.",
            remote_ref=remote_ref,
        )


def _checkout_cut_branch(root: Path, cut_branch: str, remote_ref: str) -> None:
    """Checkout or recreate the cut branch from the remote release branch tip."""
    _get("print_info")(
        MESSAGES.release.creating_release_branch.format(branch=cut_branch),
        prefix=False,
    )
    proc = _get("run_subprocess")(
        ["git", "checkout", "-B", cut_branch, remote_ref],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise GitOperationError(
            f"Failed to create release branch {cut_branch}: {proc.stderr}",
            operation="checkout_release_branch",
        )
    _get("print_success")(
        MESSAGES.release.branch_created.format(branch=cut_branch),
        prefix=False,
    )


def _apply_cut_modifications(root: Path, version: str, sync_docs: bool) -> None:
    """Apply version bumps to pyproject, init, uv.lock, and optionally docs."""
    if _update_pyproject_version(root, version):
        _get("print_info")(MESSAGES.release.updated_pyproject.format(version=version), prefix=False)
    if _update_init_version(root, version):
        _get("print_info")(MESSAGES.release.updated_init.format(version=version), prefix=False)
    if _update_uv_lock_version(root, version):
        _get("print_info")(f"Updated {CONST_UV_LOCK_FILENAME} to version {version}.", prefix=False)
    if sync_docs:
        generator = _get("DocGenerator")(root_dir=root)
        generator.write_all_docs(output_dir=root / "docs", sync_readme_table=True)


def _commit_and_push_cut_branch(
    root: Path, cut_branch: str, release_title: str, commit: bool
) -> None:
    """Stage modified files, optionally commit, and push cut branch to remote with force-with-lease."""
    if commit:
        _get("run_subprocess")(["git", "add", *_release_paths(root)], cwd=root)
        commit_proc = _get("run_subprocess")(
            ["git", "commit", "-m", release_title],
            cwd=root,
            capture_output=True,
            check=False,
        )
        if commit_proc.returncode != 0 and "nothing to commit" not in str(commit_proc.stdout):
            raise GitOperationError(
                f"Failed to create release commit: {commit_proc.stderr or commit_proc.stdout}",
                operation="create_release_commit",
            )

    _run_remote_git_or_exit(
        root,
        f"Failed to push {cut_branch} to origin",
        "push",
        "--force-with-lease",
        "-u",
        "origin",
        cut_branch,
    )


def milestone_issues_args(milestone_tag: str) -> list[str]:
    """The `gh` arguments that list the issue numbers in milestone `milestone_tag`."""
    return [
        *("issue", "list", "--milestone", milestone_tag, "--state", "all"),
        *("--json", "number", "--limit", "100"),
    ]


def milestone_pull_requests_args(milestone_tag: str) -> list[str]:
    """The `gh` arguments that list the pull requests in milestone `milestone_tag`."""
    search = f"milestone:{milestone_tag}"
    return [
        *("pr", "list", "--search", search, "--state", "all"),
        *("--json", "number,title", "--limit", "100"),
    ]


def _fetch_raw_milestone_issue_numbers(
    run_gh_fn: Any, repo_root: Path, milestone_tag: str
) -> set[int]:
    """Fetch all open and closed issue numbers associated with milestone."""
    proc = run_gh_fn(
        milestone_issues_args(milestone_tag),
        cwd=repo_root,
        quiet=True,
        use_cache=False,
    )
    if proc.returncode != 0 or not proc.stdout:
        return set()
    try:
        raw_issues = json.loads(proc.stdout)
        return {int(iss["number"]) for iss in raw_issues if iss.get("number")}
    except ValueError, TypeError, KeyError:
        return set()


def _fetch_raw_milestone_pr_numbers(
    run_gh_fn: Any, repo_root: Path, milestone_tag: str, existing_issue_numbers: set[int]
) -> set[int]:
    """Fetch standalone PR numbers associated with milestone that don't close an existing issue."""
    pr_proc = run_gh_fn(
        milestone_pull_requests_args(milestone_tag),
        cwd=repo_root,
        quiet=True,
        use_cache=False,
    )
    if pr_proc.returncode != 0 or not pr_proc.stdout:
        return set()
    try:
        raw_prs = json.loads(pr_proc.stdout)
        standalone_prs = set()
        for pr in raw_prs:
            if not pr.get("number"):
                continue
            pr_num = int(pr["number"])
            title = pr.get("title", "")
            referenced = {int(m) for m in re.findall(r"#(\d+)", title)}
            if not referenced.intersection(existing_issue_numbers):
                standalone_prs.add(pr_num)
        return standalone_prs
    except ValueError, TypeError, KeyError:
        return set()


def _query_gh_milestone_issues(repo_root: Path, milestone_tag: str) -> list[str]:
    """Query GitHub milestone issues and deliverables via rate-managed run_gh."""
    try:
        run_gh_fn = _get("run_gh")
        issue_nums = _fetch_raw_milestone_issue_numbers(run_gh_fn, repo_root, milestone_tag)
        pr_nums = _fetch_raw_milestone_pr_numbers(run_gh_fn, repo_root, milestone_tag, issue_nums)
        all_nums = issue_nums | pr_nums
        if all_nums:
            return [f"- #{num}" for num in sorted(all_nums)]
    except (OSError, ValueError, TypeError, KeyError, DevOpsCLIError) as exc:
        logger.debug("Failed to query GitHub milestone issues for %s: %s", milestone_tag, exc)
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
    except (OSError, ValueError, TypeError, DevOpsCLIError) as exc:
        logger.debug("Failed to query branch commit deliverables for %s: %s", branch_name, exc)
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
    except (OSError, ValueError, TypeError, DevOpsCLIError) as exc:
        logger.debug("Failed to extract branch release notes: %s", exc)
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

    sections = [
        f"## {pr_title}",
        f"### Summary\nRelease `v{cleaned_ver}` tracking PR under GitHub pull request merge controls.",
    ]

    if deliverables:
        heading = "### Target Milestone Deliverables" if draft else "### Included Deliverables"
        sections.append(f"{heading}\n" + "\n".join(deliverables))

    if notes:
        notes_heading = "### Release Notes\n"
        rest = len("\n\n".join(sections)) + len("\n\n") + len(notes_heading) + len("\n")
        budget = CONST_GITHUB_PULL_REQUEST_BODY_MAX_CHARS - rest
        sections.append(notes_heading + _notes_within(repo_root, cleaned_ver, notes, budget))

    return "\n\n".join(sections).strip() + "\n"


def _build_release_pr_command(
    pr_title: str,
    pr_body: str,
    base: str,
    branch_name: str,
    draft: bool,
    labels: str,
    milestone: str | None = None,
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
    if milestone:
        pr_cmd.extend(["--milestone", milestone])
    if labels:
        cleaned_labels = [lbl.strip() for lbl in labels.split(",") if lbl.strip()]
        for lbl in cleaned_labels:
            if not re.match(r"^[a-zA-Z0-9_\- /.:]+$", lbl):
                _get("print_error")(f"Invalid label '{lbl}'.", prefix=False)
                raise typer.Exit(1)
            pr_cmd.extend(["--label", lbl])
    return pr_cmd


def _execute_release_pr(pr_cmd: list[str], repo_root: Path) -> None:
    """Execute gh pr create, raising ReleasePRCreationError if pull request creation fails."""
    run_gh_fn = _get("run_gh")
    pr_proc = run_gh_fn(pr_cmd, cwd=repo_root)
    if pr_proc.returncode == 0:
        pr_url = str(pr_proc.stdout).strip()
        _get("print_success")(MESSAGES.release.pr_created.format(url=pr_url), prefix=False)
        return

    err = str(pr_proc.stderr).strip() or str(pr_proc.stdout).strip()
    msg = MESSAGES.release.pr_failed.format(error=err)
    raise ReleasePRCreationError(msg, details={"command": pr_cmd, "error": err})


def _cut_changelog_missing(version: str, missing_fragments: Sequence[int]) -> str:
    """Why the cut stops with no entries for `version`, naming the items with no fragment when
    the caller knows them, else where to find them."""
    texts = ERRORS.release
    missing = (
        texts.cut_changelog_missing_items.format(
            items=", ".join(f"#{number}" for number in missing_fragments)
        )
        if missing_fragments
        else texts.cut_changelog_missing_plan
    )
    return texts.cut_changelog_missing.format(version=version, missing=missing)


def cut_release(
    version: str | None = None,
    base: str = CONST_GIT_MAIN_BRANCH,
    draft: bool = True,
    labels: str = DEFAULT_RELEASE_LABEL,
    release_type: str = DEFAULT_RELEASE_TYPE,
    breaking: bool = False,
    sync_docs: bool = True,
    is_prepare: bool = False,
    repo_root: Path | None = None,
    edits: Callable[[Path], None] | None = None,
    missing_fragments: Sequence[int] = (),
) -> None:
    """Execute fail-closed release cut orchestration from origin release branch tip."""
    root = _get_project_root(repo_root)
    target_ver = _validate_release_version(version, root)
    cut_branch = f"release/v{target_ver}"
    release_title = _format_release_title(target_ver, prefix=release_type, breaking=breaking)

    if is_dry_run():
        render_dry_run_result(
            command="devops release pr",
            action="create_release_pull_request",
            target=target_ver,
            details={
                "version": target_ver,
                "branch": cut_branch,
                "base": base,
                "draft": draft,
                "labels": labels,
                "release_type": release_type,
                "breaking": breaking,
                "title": release_title,
                "changelog_fragments": _present_fragment_names(root),
            },
        )
        return

    _verify_clean_tree(root)
    release_branch = f"release/v{target_ver}"
    remote_ref = f"origin/{release_branch}"
    _fetch_remote_release_tip(root, release_branch)
    _get("check_argocd_gate")(root, ref=remote_ref)
    _checkout_cut_branch(root, cut_branch, remote_ref)

    if is_prepare:
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        collection = _plan_fragment_collection(root, target_ver, today)
        if collection is None and not _extract_changelog_notes(root, target_ver):
            raise ValidationError(
                _cut_changelog_missing(target_ver, missing_fragments), field="changelog"
            )
        _apply_cut_modifications(root, target_ver, sync_docs=sync_docs)
        if collection is not None:
            _write_version_changelog(root, target_ver, today, collection)
            _get("print_info")(
                MESSAGES.release.updated_changelog.format(version=target_ver, date=today),
                prefix=False,
            )
        if edits is not None:
            edits(root)
    else:
        tip_ver = _get_pyproject_version(root)
        if tip_ver:
            target_ver = tip_ver.lstrip("v").strip()
            release_title = _format_release_title(
                target_ver, prefix=release_type, breaking=breaking
            )

    _commit_and_push_cut_branch(
        root=root,
        cut_branch=cut_branch,
        release_title=release_title,
        commit=is_prepare,
    )

    _get("print_info")(
        MESSAGES.release.creating_release_pr.format(version=target_ver), prefix=False
    )
    pr_body = _build_release_pr_body(
        repo_root=root,
        target_ver=target_ver,
        base=base,
        branch_name=cut_branch,
        draft=draft,
        pr_title=release_title,
    )
    pr_cmd = _build_release_pr_command(
        pr_title=release_title,
        pr_body=pr_body,
        base=base,
        branch_name=cut_branch,
        draft=draft,
        labels=labels,
        milestone=f"v{target_ver.lstrip('v')}",
    )
    _execute_release_pr(pr_cmd=pr_cmd, repo_root=root)
