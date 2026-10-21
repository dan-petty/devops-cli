"""Multi-persona review execution runner, model warming, and session management."""

from __future__ import annotations

import hashlib
import logging
from collections import Counter
from collections.abc import Mapping, Sequence
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict

from devops_cli.ai.analyze.cache import _load_file_analysis_metas
from devops_cli.ai.analyze.symbols import BaseRevision
from devops_cli.ai.client import get_llm_client
from devops_cli.ai.personas import PERSONAS, Persona, PersonaDefinition
from devops_cli.ai.review.flags import ReviewStageFlags
from devops_cli.ai.review.path_classes import load_path_classes, load_review_config
from devops_cli.ai.review.profile import (
    ReviewProfile,
    ReviewProfiler,
    active_profiler,
    profiling,
    report_profile,
    review_stage,
)
from devops_cli.ai.review.protocol import ReviewLLMClient
from devops_cli.ai.review.review_environment import (
    _get_reviews_base_dir as _get_reviews_base_dir,
)
from devops_cli.ai.review_schema import (
    Finding,
    ReviewResult,
    SavedFinding,
    compute_verdict_distributions,
    parse_review_response,
)
from devops_cli.config.constants import (
    CONST_GIT_MAIN_BRANCH,
    CONST_GIT_NAME_STATUS_CHANGE_TYPES,
    CONST_GITHUB_PR_FILE_CHANGE_TYPES,
)
from devops_cli.config.defaults import (
    DEFAULT_REVIEW_MAX_DIFF_CHARS,
    DEFAULT_REVIEW_TIMEOUT_SECONDS,
)
from devops_cli.config.settings import Settings, load_settings
from devops_cli.core.process import run_subprocess as _run_subprocess
from devops_cli.core.repo import find_repo_root, is_ignored_by_git, is_safe_subpath
from devops_cli.dry_run import is_dry_run
from devops_cli.models.ai import FileAnalysisMeta
from devops_cli.models.git import ChangedFile
from devops_cli.output import (
    format_duration,
    print_error,
    print_info,
    print_section,
    print_table,
    print_warning,
)
from devops_cli.review.diff import (
    diff_blocks,
    diff_file_names,
    number_source_lines,
)
from devops_cli.review.suppression import (
    covering_suppressions,
    format_covering_suppressions,
    load_review_suppressions,
)
from devops_cli.review.targets import (
    is_secret_scan_only,
)
from devops_cli.security.sanitizer import (
    redact_text,
)
from devops_cli.telemetry import trace_span

if TYPE_CHECKING:
    from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator

logger = logging.getLogger(__name__)

_MAX_DIFF_CHARS = DEFAULT_REVIEW_MAX_DIFF_CHARS


class ReviewClients(BaseModel):
    """LLM client resolved for review analysis."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    analysis: ReviewLLMClient | None = None


def _debug_block(title: str, payload: dict[str, Any]) -> None:
    from devops_cli.output import print_dry_run_result

    print_warning(f"[dry-run] {title}", prefix=False)
    print_dry_run_result(payload)


def _find_session_dir(session_arg: str | None) -> Path | None:
    reviews_dir = _get_reviews_base_dir()
    if not reviews_dir.exists():
        return None
    if session_arg:
        safe_arg = Path(session_arg).name
        target = (reviews_dir / safe_arg).resolve()
        if target.exists() and target.is_dir() and target.is_relative_to(reviews_dir.resolve()):
            return target
        matches = [d for d in reviews_dir.iterdir() if d.is_dir() and safe_arg in d.name]
        if matches:
            return sorted(matches)[-1]
        return None

    sessions = [d for d in reviews_dir.iterdir() if d.is_dir() and (d / "findings.json").exists()]
    return max(sessions, key=lambda p: p.stat().st_mtime) if sessions else None


def _format_finding_markdown(f: Finding) -> list[str]:
    """Format an individual finding for markdown output."""
    verified = ""
    if f.mitigated:
        verified = " *(mitigated)*"
    elif not f.verified:
        verified = " *(unverified)*"
    lines = [
        f"### [{f.severity}] {f.title}{verified}",
        f"**Location:** `{f.location}`\n",
    ]
    if f.description:
        lines.append(f"{f.description}\n")
    if f.fix:
        lines.append(f"**Fix:** {f.fix}\n")
    if f.references:
        lines.append(f"**References:** {', '.join(f.references)}\n")
    return lines


def _review_to_markdown(review: ReviewResult | str) -> str:
    if isinstance(review, str):
        from devops_cli.ai.thinking_stream import strip_think_blocks

        clean_text = strip_think_blocks(review)
        parsed = parse_review_response(clean_text)
        return _review_to_markdown(parsed) if parsed else clean_text
    if getattr(review, "report_markdown", None):
        return str(review.report_markdown)
    lines: list[str] = [f"**Recommendation: {review.recommendation}**\n"]
    if review.findings:
        lines.append("## Findings\n")
        for f in review.sorted_findings:
            lines.extend(_format_finding_markdown(f))
    if review.summary:
        lines.append("## Model Notes (Not Verified)\n")
        lines.append(review.summary)
    return "\n".join(lines)


def _has_review_findings(reviews: list[tuple[PersonaDefinition, ReviewResult | str]]) -> bool:
    """Return True if any review contains actionable findings."""
    for _, rev in reviews:
        if isinstance(rev, ReviewResult) and any(
            getattr(f, "reportable", True) for f in rev.findings
        ):
            return True
        if isinstance(rev, str):
            from devops_cli.ai.thinking_stream import strip_think_blocks
            from devops_cli.core.serialization import extract_json_block

            clean = strip_think_blocks(rev)
            parsed = extract_json_block(clean, default=None)
            if isinstance(parsed, dict) and parsed.get("findings"):
                return True
            if "## Detailed Findings" in clean or "### [" in clean:
                return True
    return False


def _extract_review_summaries(
    reviews: list[tuple[PersonaDefinition, ReviewResult | str]],
) -> list[tuple[str, str]]:
    """Extract non-empty summaries from persona reviews."""
    summaries: list[tuple[str, str]] = []
    for pd, rev in reviews:
        text = ""
        if isinstance(rev, ReviewResult) and rev.summary:
            text = rev.summary.strip()
        elif isinstance(rev, str):
            from devops_cli.ai.thinking_stream import strip_think_blocks
            from devops_cli.core.serialization import extract_json_block

            clean = strip_think_blocks(rev)
            parsed = extract_json_block(clean, default=None)
            if isinstance(parsed, dict) and parsed.get("summary"):
                text = str(parsed["summary"]).strip()
        if text:
            summaries.append((pd.title, text))
    return summaries


def _format_zero_findings_comment(
    reviews: list[tuple[PersonaDefinition, ReviewResult | str]],
    files: list[str] | None,
    static_analyzers: dict[str, str] | None,
) -> str:
    """Construct fixed zero-findings comment naming files, personas, and analyzers that ran."""
    files_list = files or []
    files_str = ", ".join(f"`{f}`" for f in files_list) if files_list else "None"
    personas_str = ", ".join(pd.title for pd, _ in reviews) if reviews else "None"

    if static_analyzers:
        ran = [
            name
            for name, state in static_analyzers.items()
            if state in ("ran", "built-in patterns")
        ]
        analyzers_str = ", ".join(sorted(ran)) if ran else "None"
    else:
        analyzers_str = "None"

    lines = [
        "## 🤖 AI Code Review\n",
        "Zero findings identified.\n",
        f"- **Files checked:** {files_str}",
        f"- **Personas:** {personas_str}",
        f"- **Analyzers:** {analyzers_str}",
    ]

    summaries = _extract_review_summaries(reviews)
    if summaries:
        lines.append("\n## Model Notes (Not Verified)\n")
        if len(summaries) == 1:
            lines.append(summaries[0][1])
        else:
            for persona_title, summary_text in summaries:
                lines.append(f"### {persona_title}\n\n{summary_text}\n")

    return "\n".join(lines).strip() + "\n"


def format_pr_review_comment(
    reviews: list[tuple[PersonaDefinition, ReviewResult | str]],
    files: list[str] | None = None,
    target_dir: Path | None = None,
    static_analyzers: dict[str, str] | None = None,
) -> str:
    """Format PR comment body for post_comment review workflow.

    Emits a fixed zero-findings comment naming files, personas, and analyzers when zero
    findings are identified, routing model suggestions under 'Model Notes (Not Verified)'.
    Emits persona finding sections when findings exist.
    """
    if not reviews:
        return ""

    if is_dry_run():
        effective_analyzers: dict[str, str] = {}
    elif static_analyzers is not None:
        effective_analyzers = static_analyzers
    else:
        analyzers_found = None
        for _, rev in reviews:
            if isinstance(rev, ReviewResult) and getattr(rev, "static_analyzers", None) is not None:
                analyzers_found = rev.static_analyzers
                break
        effective_analyzers = analyzers_found if analyzers_found is not None else {}

    if not _has_review_findings(reviews):
        return _format_zero_findings_comment(reviews, files, effective_analyzers)

    sections = "\n\n---\n\n".join(
        f"## Review by {pd.title}\n\n{_review_to_markdown(text)}" for pd, text in reviews
    )
    return f"## 🤖 AI Code Review\n\n{sections}\n"


def _nearest_conventions(start: Path, revision: str | None = None) -> str:
    """Return the nearest project conventions file, from the start directory up to its repo root,
    as it was at `revision` when one is given."""
    from devops_cli.ai.review.review_environment import nearest_conventions

    return nearest_conventions(start, revision)


def _git_repo_root(path: Path) -> Path | None:
    root = find_repo_root(path)
    return root if (root / ".git").exists() else None


def _list_git_tracked_candidates(
    root: Path, repo_root: Path | None
) -> tuple[list[Path], bool, bool]:
    """Retrieve git-tracked candidate file paths when inside a repository."""
    if repo_root is None:
        return [p for p in sorted(root.rglob("*")) if p.is_file()], False, False

    try:
        rel_to_repo = root.relative_to(repo_root)
        rel_str = str(rel_to_repo) if str(rel_to_repo) != "." else "."
    except ValueError:
        rel_str = "."

    root_ignored = (
        is_ignored_by_git(repo_root, root) if root.resolve() != repo_root.resolve() else False
    )
    if not root_ignored:
        result = _run_subprocess(
            [
                "git",
                "-C",
                str(repo_root),
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "-z",
                "--",
                rel_str,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout:
            candidates = [repo_root / Path(item) for item in result.stdout.split("\0") if item]
            return candidates, True, root_ignored

    fallback_candidates = [p for p in sorted(root.rglob("*")) if p.is_file()]
    return fallback_candidates, False, root_ignored


def _is_candidate_file_included(
    candidate_path: Path,
    root: Path,
    repo_root: Path | None,
    is_from_git: bool,
    root_ignored: bool,
    pattern: str,
) -> bool:
    """Predicate determining if candidate file should be included in review scope."""
    if not candidate_path.is_file():
        return False
    effective_root = repo_root or find_repo_root(candidate_path)
    if not is_from_git and not root_ignored and is_ignored_by_git(effective_root, candidate_path):
        return False

    try:
        rel = candidate_path.relative_to(root)
    except ValueError:
        rel = candidate_path
    return rel.match(pattern)


def _review_label(path: Path, root: Path, repo_root: Path | None) -> Path:
    """A collected file's name in review pages: relative to its repository, else to the root."""
    if repo_root is not None and path.is_relative_to(repo_root):
        return path.relative_to(repo_root)
    return path.relative_to(root) if path.is_relative_to(root) else path


def _partition_candidate_files(root: Path, pattern: str) -> tuple[list[Path], list[Path]]:
    """The files under root a path review reads, in review order, and those it routes to the
    secret scan alone (`is_secret_scan_only`, #948, #1151)."""
    repo_root = _git_repo_root(root)
    candidates, is_from_git, root_ignored = _list_git_tracked_candidates(root, repo_root)
    reviewed: list[Path] = []
    routed: list[Path] = []
    for p in sorted(candidates):
        if _is_candidate_file_included(p, root, repo_root, is_from_git, root_ignored, pattern):
            skipped = is_secret_scan_only(_review_label(p, root, repo_root))
            (routed if skipped else reviewed).append(p)
    return reviewed, routed


def _review_candidate_files(root: Path, pattern: str) -> list[Path]:
    """The files under root that a path review reads, in review order."""
    return _partition_candidate_files(root, pattern)[0]


def _routed_changes(
    base_revision: BaseRevision | None,
    path_classes: Mapping[str, Sequence[str]] | None = None,
) -> list[str]:
    """The files a branch or pull request changed that review skips, for the secret scan; a
    deleted file has nothing left to scan."""
    if base_revision is None:
        return []
    deleted = CONST_GIT_NAME_STATUS_CHANGE_TYPES["D"]
    return [
        change.path
        for change in base_revision.changes
        if change.change_type != deleted
        and is_secret_scan_only(change.path, path_classes=path_classes)
    ]


def _file_blocks(root: Path, files: Sequence[Path]) -> list[str]:
    """The review blocks of files collected under root, each under its review label."""
    blocks: list[str] = []
    repo_root = _git_repo_root(root)

    for p in files:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        file_label = _review_label(p, root, repo_root)
        suffix = file_label.suffix.lstrip(".") or "text"
        numbered = number_source_lines(text)
        blocks.append(f"### File: {file_label}\n```{suffix}\n{numbered.removesuffix(chr(10))}\n```")
    return blocks


def _collect_file_blocks(root: Path, pattern: str) -> list[str]:
    return _file_blocks(root, _review_candidate_files(root, pattern))


def _corpus_digest(targets: list[Path], pattern: str) -> str:
    """Fingerprint the files a path review reads, so benchmarks of the same corpus can be matched."""
    digest = hashlib.sha256()
    for target in targets:
        resolved = target.resolve()
        if resolved.is_file():
            digest.update(resolved.read_bytes())
            continue
        for block in _collect_file_blocks(resolved, pattern):
            digest.update(block.encode())
    return digest.hexdigest()[:16]


def _print_analysis_metadata(analysis_metas: dict[str, FileAnalysisMeta], title: str) -> None:
    """Render a summary table of file analysis metadata."""
    print_section(f"Analysis Metadata — {title}", style="bold cyan")
    if not analysis_metas:
        print_warning("No analysis metadata found for files in scope.", prefix=False)
        return
    columns = [
        ("File Path", "cyan"),
        ("Language", "green"),
        ("Purpose", "white"),
        ("Complexity", "magenta"),
    ]
    rows = [
        [
            path,
            fmeta.language or "text",
            fmeta.primary_purpose or "—",
            fmeta.complexity_score or "—",
        ]
        for path, fmeta in analysis_metas.items()
    ]
    print_table(columns=columns, rows=rows)


def _make_review_clients(
    settings: Any,
    *,
    cache_enabled: bool | None = None,
    append_cache: bool | None = None,
) -> ReviewClients:
    """Build LLM client for review analysis."""
    task_config = settings.ai.for_task("analysis")
    return ReviewClients(
        analysis=get_llm_client(
            task="analysis",
            settings=settings,
            request_timeout_seconds=task_config.timeout or DEFAULT_REVIEW_TIMEOUT_SECONDS,
            cache_enabled=cache_enabled,
            append_cache=append_cache,
        )
    )


def _is_allowed_review_boundary(target: Path, settings: Settings) -> bool:
    target_resolved = target.resolve()
    allowed_roots: list[Path] = [Path.cwd().resolve()]
    if (cwd_repo := _git_repo_root(Path.cwd())) is not None:
        allowed_roots.append(cwd_repo.resolve())
    if (target_repo := _git_repo_root(target_resolved)) is not None:
        allowed_roots.append(target_repo.resolve())

    repos_base = settings.repos.base_dir.resolve()
    allowed_roots.append(repos_base)

    return any(is_safe_subpath(root, target_resolved) for root in allowed_roots)


def _detect_remote_default_branch(repo_path: Path) -> str:
    """The origin's default branch as `origin/<name>`, or empty when the clone records none."""
    res_sym = _run_subprocess(
        ["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
        capture_output=True,
        text=True,
        cwd=repo_path,
        check=False,
    )
    return res_sym.stdout.strip() if res_sym.returncode == 0 and res_sym.stdout else ""


def _detect_base_branch(repo_path: Path, preferred_base: str = CONST_GIT_MAIN_BRANCH) -> str:
    """The branch a review diffs against: `preferred_base`, else main, master or trunk, else the
    origin's default branch, each local or else as `origin/<name>`.

    The base is never the checked-out branch for want of another. A single-branch clone or a
    CI checkout of a feature has no local `main`, and taking the feature as its own base
    reviewed only its last commit, under conventions its earlier commits set (#946). With no
    base found, `preferred_base` is returned and the diff against it fails.
    """
    res = _run_subprocess(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{preferred_base}"],
        capture_output=True,
        text=True,
        cwd=repo_path,
        check=False,
    )
    if res.returncode == 0:
        return preferred_base

    branches_proc = _run_subprocess(
        ["git", "for-each-ref", "--format=%(refname:short)", "refs/heads/", "refs/remotes/origin/"],
        capture_output=True,
        text=True,
        cwd=repo_path,
        check=False,
    )
    branches = (
        {b.strip() for b in branches_proc.stdout.splitlines() if b.strip()}
        if branches_proc.returncode == 0
        else set()
    )

    def local_or_remote(name: str) -> str | None:
        if name in branches:
            return name
        return f"origin/{name}" if f"origin/{name}" in branches else None

    if base := local_or_remote(preferred_base):
        return base
    for alt in ("main", "master", "trunk"):
        if alt in branches:
            return alt
    if remote_default := _detect_remote_default_branch(repo_path):
        return local_or_remote(remote_default.removeprefix("origin/")) or remote_default
    for alt in ("main", "master", "trunk"):
        if f"origin/{alt}" in branches:
            return f"origin/{alt}"

    return str(preferred_base)


def _prepare_path_content(target: Path, pattern: str) -> tuple[list[str], str, list[str]]:
    """Prepare paginated pages, title, and the files kept off the pages for the secret scan
    alone, for a path review target."""
    import typer

    from devops_cli.config.constants import CONST_MAX_FILE_SIZE_BYTES
    from devops_cli.lang import MESSAGES

    settings = load_settings()
    target_resolved = target.resolve()
    if not _is_allowed_review_boundary(target, settings):
        err_msg = MESSAGES.review.outside_boundary.format(target=target_resolved)
        print_error(err_msg, prefix=False)
        raise typer.Exit(1)
    if target_resolved.is_file():
        if target_resolved.stat().st_size > CONST_MAX_FILE_SIZE_BYTES:
            max_mb = CONST_MAX_FILE_SIZE_BYTES // (1024 * 1024)
            err_size = MESSAGES.review.exceeds_max_size.format(
                target=target_resolved, max_mb=max_mb
            )
            print_error(err_size, prefix=False)
            raise typer.Exit(0)
        repo_root = _git_repo_root(target_resolved)
        file_label = (
            str(target_resolved.relative_to(repo_root))
            if repo_root and target_resolved.is_relative_to(repo_root)
            else target_resolved.name
        )
        suffix = target_resolved.suffix.lstrip(".") or "text"
        content = target_resolved.read_text(encoding="utf-8", errors="replace")
        numbered = number_source_lines(content)
        blocks = [f"### File: {file_label}\n```{suffix}\n{numbered.removesuffix(chr(10))}\n```"]
        title = str(file_label)
        # A file named as the target is reviewed as asked.
        routed: list[str] = []
    else:
        collecting_msg = MESSAGES.review.collecting_files.format(
            pattern=f"[cyan]{pattern}[/cyan]", target=f"[dim]{target_resolved}[/dim]"
        )
        print_info(collecting_msg, prefix=False)
        reviewed, routed_paths = _partition_candidate_files(target_resolved, pattern)
        blocks = _file_blocks(target_resolved, reviewed)
        repo_root = _git_repo_root(target_resolved)
        routed = [_review_label(p, target_resolved, repo_root).as_posix() for p in routed_paths]
        title = str(target_resolved)

    if not blocks and not routed:
        print_warning(MESSAGES.review.no_files_found, prefix=False)
        raise typer.Exit(0)

    pages = [redact_text(p) for p in blocks]
    return pages, title, routed


def _get_current_git_branch(repo_path: Path) -> str:
    """Return active git branch name if HEAD is attached, otherwise empty string."""
    proc = _run_subprocess(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        cwd=repo_path,
        check=False,
    )
    if proc.returncode == 0 and (name := proc.stdout.strip()) and name != "HEAD":
        return name
    return ""


def _has_uncommitted_working_tree_changes(repo_path: Path) -> bool:
    """Return True if working tree has staged or unstaged modifications."""
    proc = _run_subprocess(
        ["git", "diff", "HEAD"],
        capture_output=True,
        text=True,
        cwd=repo_path,
        check=False,
    )
    return proc.returncode == 0 and bool(proc.stdout.strip())


def _resolve_main_branch_fallback_base(repo_path: Path, branch_name: str) -> str:
    """Find appropriate comparison base when reviewing main/primary branch."""
    from devops_cli.git.operations import get_latest_git_tag

    tag = get_latest_git_tag(repo_path)
    if tag:
        tag_diff = _run_subprocess(
            ["git", "diff", f"{tag}...{branch_name}"],
            capture_output=True,
            text=True,
            cwd=repo_path,
            check=False,
        )
        if tag_diff.returncode == 0 and tag_diff.stdout.strip():
            return tag

    parent_proc = _run_subprocess(
        ["git", "rev-parse", "--verify", "--quiet", f"{branch_name}~1"],
        capture_output=True,
        text=True,
        cwd=repo_path,
        check=False,
    )
    if parent_proc.returncode == 0:
        return f"{branch_name}~1"

    return "HEAD"


def _resolve_branch_targets(
    repo_path: Path, branch_name: str | None, base: str
) -> tuple[str, str, bool]:
    """Resolve target branch and comparison base, handling main branch review edge cases."""
    current_branch = _get_current_git_branch(repo_path)
    target_branch = branch_name or current_branch
    if not target_branch:
        return "", "", False

    effective_base = _detect_base_branch(repo_path, base)

    # When target branch equals effective base (e.g. both are 'main')
    if target_branch == effective_base:
        if current_branch and current_branch != target_branch:
            # User passed base branch while on another branch (e.g. 'devops review branch main' from release/v0.2.20)
            return current_branch, effective_base, False

        # User is reviewing main branch directly
        if _has_uncommitted_working_tree_changes(repo_path):
            return target_branch, "HEAD", True

        fallback_base = _resolve_main_branch_fallback_base(repo_path, target_branch)
        return target_branch, fallback_base, False

    return target_branch, effective_base, False


def _branch_base_revision(
    repo_path: Path, effective_base: str, target_branch: str, is_working_tree: bool
) -> BaseRevision:
    """Where a branch review's diff starts, the files it changed, and readers for their text.

    A working-tree review starts at `HEAD` and ends at the files on disk. A branch starts at the
    merge base of the base and the target, as `git diff base...target` does; with none, the
    review falls back to a two-dot diff from `effective_base`, and so does this. It ends at the
    target's commit, which is read there: the checkout can be another branch, or carry edits
    the diff leaves out, and its text would count their removals as the branch's.
    """
    from devops_cli.git.operations import (
        list_changed_files,
        read_file_at_revision,
        resolve_merge_base,
    )

    head = None if is_working_tree else target_branch
    revision = (
        "HEAD"
        if head is None
        else resolve_merge_base(repo_path, effective_base, head) or effective_base
    )
    changes = tuple(list_changed_files(repo_path, revision, head))
    return BaseRevision(
        changes=changes,
        read=partial(read_file_at_revision, repo_path, revision),
        read_head=None if head is None else partial(read_file_at_revision, repo_path, head),
        revision=revision,
    )


def _prepare_branch_content(
    branch_name: str | None, base: str, repo_path: Path
) -> tuple[list[str], str, str, BaseRevision]:
    """Prepare diff blocks, title, resolved target_branch, and the base
    revision the diff starts from."""
    import typer

    from devops_cli.lang import MESSAGES

    settings = load_settings()
    repo_resolved = repo_path.resolve()
    if not _is_allowed_review_boundary(repo_resolved, settings):
        err_msg = MESSAGES.review.outside_boundary.format(target=repo_resolved)
        print_error(err_msg, prefix=False)
        raise typer.Exit(1)

    target_branch, effective_base, is_working_tree = _resolve_branch_targets(
        repo_path, branch_name, base
    )
    if not target_branch:
        print_error(MESSAGES.review.detect_branch_failed, prefix=False)
        raise typer.Exit(1)

    diffing_msg = MESSAGES.review.diffing_branches.format(
        branch=f"[cyan]{target_branch}[/cyan]", base=f"[cyan]{effective_base}[/cyan]"
    )
    print_info(diffing_msg, prefix=False)

    if is_working_tree:
        diff_proc = _run_subprocess(
            ["git", "diff", "HEAD"],
            capture_output=True,
            text=True,
            cwd=repo_path,
        )
    else:
        diff_proc = _run_subprocess(
            ["git", "diff", f"{effective_base}...{target_branch}"],
            capture_output=True,
            text=True,
            cwd=repo_path,
        )
        if diff_proc.returncode != 0:
            diff_proc = _run_subprocess(
                ["git", "diff", effective_base, target_branch],
                capture_output=True,
                text=True,
                cwd=repo_path,
            )
    if diff_proc.returncode != 0:
        diff_err = MESSAGES.review.git_diff_failed.format(error=diff_proc.stderr.strip())
        print_error(diff_err, prefix=False)
        raise typer.Exit(1)
    if not diff_proc.stdout.strip():
        print_warning(MESSAGES.review.no_diff_found, prefix=False)
        raise typer.Exit(0)

    title = f"Branch `{target_branch}` vs `{effective_base}`"
    base_revision = _branch_base_revision(repo_path, effective_base, target_branch, is_working_tree)
    path_classes = load_path_classes(base_revision=base_revision)
    pages = [redact_text(p) for p in diff_blocks(diff_proc.stdout, path_classes=path_classes)]
    return pages, title, target_branch, base_revision


def _prepare_pr_content(
    number: int,
    repo_arg: str | None = None,
    **kwargs: Any,
) -> tuple[list[str], str, Any, str, BaseRevision | None]:
    """Fetch PR details, diff blocks, and title for PR review target.

    With `head_dir`, the PR head's changed files are written under it, and the base revision
    they are compared with is returned; without it, there is none.
    """
    import typer

    from devops_cli.github.session import get_github_session
    from devops_cli.lang import MESSAGES

    repo = repo_arg
    if repo is None:
        from devops_cli.core.repo import get_repo_origin_name

        repo = get_repo_origin_name()
        if not repo:
            parse_err = MESSAGES.review.github_repo_parse_failed.format(raw="")
            print_error(parse_err, prefix=False)
            raise typer.Exit(1)

    fetch_msg = MESSAGES.review.fetching_pr.format(number=number, repo=f"[cyan]{repo}[/cyan]")
    print_info(fetch_msg, prefix=False)
    gh = get_github_session().client
    pull = gh.get_pull(repo, number)
    diff = gh.get_pr_diff(repo, number)
    title = f"PR #{number}: {pull.title}"
    head_dir: Path | None = kwargs.get("head_dir")
    base_revision: BaseRevision | None = None
    if head_dir is not None:
        pr_files = list(pull.get_files())
        _materialize_pr_head(gh, repo, pull, head_dir, pr_files)
        base_revision = _pr_base_revision(gh, repo, pull, pr_files)
    path_classes = load_path_classes(base_revision=base_revision)
    pages = [redact_text(p) for p in diff_blocks(diff, path_classes=path_classes)]
    return pages, title, pull, repo, base_revision


def _pr_changed_file(pr_file: Any) -> ChangedFile:
    """A pull request file as a change: its status, head path and, if renamed, its old path."""
    return ChangedFile(
        change_type=CONST_GITHUB_PR_FILE_CHANGE_TYPES.get(str(pr_file.status), "unknown"),
        path=pr_file.filename,
        old_path=getattr(pr_file, "previous_filename", None) or None,
    )


def _pr_base_revision(gh: Any, repo: str, pull: Any, pr_files: Sequence[Any]) -> BaseRevision:
    """The PR's changed files, and a reader for their text at its merge base in the base repo.

    `pull.base.sha` is the base branch's tip, which can be ahead of the merge base: read there,
    a PR branched earlier would list symbols added on the base since as removed. When the merge
    base cannot be read, nothing is read, and a modified file's delta stays unknown.
    """
    base_obj = getattr(pull, "base", None)
    base_repo = getattr(getattr(base_obj, "repo", None), "full_name", None) or repo
    base_sha = getattr(base_obj, "sha", None)
    head_sha = getattr(getattr(pull, "head", None), "sha", None)
    merge_base = gh.get_merge_base(base_repo, base_sha, head_sha) if base_sha and head_sha else None
    if merge_base is None:
        logger.debug("No merge base for %s...%s in %s", base_sha, head_sha, base_repo)

    def read(path: str) -> str | None:
        return gh.get_file_at(base_repo, path, merge_base) if merge_base else None

    return BaseRevision(changes=tuple(_pr_changed_file(f) for f in pr_files), read=read)


def _materialize_pr_head(gh: Any, repo: str, pull: Any, dest: Path, pr_files: Sequence[Any]) -> int:
    """Write PR head's version of changed files, and base conventions, under `dest`."""
    from devops_cli.ai.review.review_environment import _TARGET_CONVENTIONS_CANDIDATES
    from devops_cli.config.constants import CONST_REVIEW_CONVENTIONS_FILE

    head_obj = getattr(pull, "head", None)
    base_obj = getattr(pull, "base", None)
    head_repo = getattr(getattr(head_obj, "repo", None), "full_name", None) or repo
    base_repo = getattr(getattr(base_obj, "repo", None), "full_name", None) or repo
    base_ref = getattr(base_obj, "sha", None) or getattr(base_obj, "ref", None) or "main"
    head_sha = getattr(head_obj, "sha", None) or "HEAD"
    changed = [f.filename for f in pr_files if getattr(f, "status", "") != "removed"]
    convention_files = set(_TARGET_CONVENTIONS_CANDIDATES) | {CONST_REVIEW_CONVENTIONS_FILE}
    root = dest.resolve()
    written = 0

    for rel in convention_files:
        target = (root / rel).resolve()
        if not target.is_relative_to(root):
            continue
        text = gh.get_file_at(base_repo, rel, base_ref) if gh else None
        if text is None and (gh is None or not base_repo):
            local_conv = Path.cwd() / rel
            if local_conv.exists() and local_conv.is_file():
                text = local_conv.read_text(encoding="utf-8")
        if text is not None:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
            written += 1

    for rel in changed:
        if rel in convention_files:
            continue
        target = (root / rel).resolve()
        if not target.is_relative_to(root):
            continue
        text = gh.get_file_at(head_repo, rel, head_sha)
        if text is None:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        written += 1

    return written


def _record_profile_findings(payloads: list[Any], candidates: int) -> None:
    """Record candidate, verified and reported finding counts on the active review profile."""
    profiler = active_profiler()
    if profiler is None:
        return
    findings = [f for p in payloads for f in p.findings]
    profiler.set_findings(
        candidates=candidates,
        verified=sum(1 for f in findings if f.verified),
        reported=sum(1 for f in findings if f.reportable),
        verdict_distributions=compute_verdict_distributions(findings),
    )


def _write_review_profile(
    profiler: ReviewProfiler, orchestrator: ReviewPipelineOrchestrator, target: str, files: int
) -> ReviewProfile:
    """Write the session's profile.json and summarise where the time went."""
    profiler.set_coverage(getattr(orchestrator, "coverage", {}))
    profiler.set_partial_context(getattr(orchestrator, "partial_context", False))
    profile = profiler.build(session_id=orchestrator.session_id, target=target, files=files)
    path = profile.write(orchestrator.session_dir)
    report_profile(profile)
    if profile.code_changed_during_run:
        from devops_cli.lang import MESSAGES

        print_warning(MESSAGES.review.code_changed_during_run, prefix=False)
    stages = ", ".join(
        f"{s.name} {format_duration(s.wall_seconds)} ({s.llm_calls} calls)"
        for s in profile.stages
        if s.wall_seconds >= 1 or s.llm_calls
    )
    capped = profile.truncated_replies
    capped_note = f", {capped} hit the reply cap" if capped else ""
    print_info(
        f"[dim]Profile: {format_duration(profile.total_wall_seconds)}, "
        f"{profile.llm_calls} LLM calls{capped_note}; {stages} -> {path}[/dim]",
        prefix=False,
    )
    return profile


def _finding_producer(finding: Finding) -> str:
    """Return the finding's producer name if set, else 'unknown'."""
    p = getattr(finding, "producer", None)
    if isinstance(p, str) and p.strip():
        return p.strip()
    return "unknown"


def _record_review_metrics(
    results: list[tuple[PersonaDefinition, ReviewResult | str]],
    seconds: float,
    target_type: str,
) -> None:
    """Send the review's wall time, and its findings by producer, severity and status."""
    from devops_cli.telemetry.instruments import FINDINGS_TOTAL, REVIEW_DURATION, emit

    emit(REVIEW_DURATION, seconds, {"target_type": target_type})
    counts = Counter(
        (_finding_producer(finding), finding.severity.upper(), finding.status.upper())
        for _, result in results
        if isinstance(result, ReviewResult)
        for finding in result.findings
    )
    for (producer_name, severity, status), count in counts.items():
        emit(
            FINDINGS_TOTAL,
            count,
            {"producer": producer_name, "severity": severity, "status": status},
        )


def _run_profiled_session(
    orchestrator: ReviewPipelineOrchestrator,
    all_files: list[str],
    target_dir: Path,
    pages: list[str],
    target_type: Literal["branch", "pr", "path"],
    target_ref: str,
    stage_flags: ReviewStageFlags | None,
    base_revision: BaseRevision | None = None,
) -> list[tuple[PersonaDefinition, ReviewResult | str]] | None:
    """Run the orchestrated review under a profiler; None when there are no files to review."""
    with profiling() as profiler:
        with review_stage("pre_analysis"):
            metadata_by_path = orchestrator.run_pre_analysis_refresh(
                target_dir=target_dir,
                target_type=target_type,
                target_ref=target_ref,
                stage_flags=stage_flags,
                base_revision=base_revision,
            )
        if not all_files:
            return None
        results = _run_orchestrator_review(
            orchestrator,
            all_files,
            metadata_by_path,
            target_dir,
            pages,
            stage_flags=stage_flags,
        )
        if not is_dry_run():
            profile = _write_review_profile(profiler, orchestrator, target_ref, len(all_files))
            _record_review_metrics(results, profile.total_wall_seconds, target_type)
        return results


def _run_orchestrator_review(
    orchestrator: ReviewPipelineOrchestrator,
    all_files: list[str],
    metadata_by_path: dict[str, FileAnalysisMeta],
    target_dir: Path | None,
    pages: list[str],
    stage_flags: ReviewStageFlags | None = None,
) -> list[tuple[PersonaDefinition, ReviewResult | str]]:
    """Execute orchestrator pipeline review for all files."""
    diff_map = {f: "\n".join(p for p in pages if f in diff_file_names(p)) for f in all_files}
    with review_stage("payloads"):
        payloads = orchestrator.init_per_file_payloads(
            all_files,
            metadata_by_path,
            target_dir=target_dir,
            stage_flags=stage_flags,
            diff_text_by_file=diff_map,
            pages=pages,
        )
    if not is_dry_run():
        candidates = sum(len(p.findings) for p in payloads)
        _record_profile_findings(payloads, candidates)

    with review_stage("report"):
        return _report_review(orchestrator, payloads, stage_flags)


def _finding_from_admitted_scanner(af: Any) -> SavedFinding:
    """Convert an admitted frozen scanner finding into a SavedFinding for review reporting."""
    loc = getattr(af, "location_display", "") or (
        f"{af.path}:{af.line}" if getattr(af, "line", None) else getattr(af, "path", "")
    )
    title = (
        f"[{af.tool}] {af.rule_id}: {af.message}"
        if getattr(af, "tool", None)
        else getattr(af, "message", "")
    )
    sf = SavedFinding(
        severity=getattr(af, "severity", "MEDIUM"),
        location=loc,
        title=title,
        description=getattr(af, "description", "") or getattr(af, "message", ""),
        fix=getattr(af, "fix", ""),
        status="VERIFIED",
        fingerprint=getattr(af, "fingerprint_v2", "") or getattr(af, "fingerprint", ""),
        producer=getattr(af, "tool", ""),
    )
    if hasattr(af, "tool"):
        object.__setattr__(sf, "_tool", af.tool)
    return sf


def _collect_review_findings(
    orchestrator: Any,
    payloads: list[Any],
    payload_data: dict[str, Any] | None,
    stage_flags: ReviewStageFlags | None,
) -> list[SavedFinding]:
    """Collect verified findings from report payload, file payloads, or admitted findings."""
    raw_findings = payload_data.get("findings", []) if isinstance(payload_data, dict) else []
    if not raw_findings and stage_flags is not None and not stage_flags.reporting:
        if hasattr(orchestrator, "_collect_and_deduplicate_findings"):
            raw_findings = orchestrator._collect_and_deduplicate_findings(payloads)
        admitted = getattr(orchestrator, "admitted_scanner_findings", None) or []
        if admitted:
            from devops_cli.review.state import FindingState

            existing_locs = {
                getattr(f, "location", "") if not isinstance(f, dict) else f.get("location", "")
                for f in raw_findings
            }
            extra_admitted = [
                _finding_from_admitted_scanner(af)
                for af in admitted
                if getattr(af, "state", None) != FindingState.SUPPRESSED
                and (getattr(af, "location_display", "") or getattr(af, "path", ""))
                not in existing_locs
            ]
            raw_findings = [*raw_findings, *extra_admitted]

    return [SavedFinding(**f) if isinstance(f, dict) else f for f in raw_findings]


def _report_review(
    orchestrator: ReviewPipelineOrchestrator,
    payloads: list[Any],
    stage_flags: ReviewStageFlags | None,
) -> list[tuple[PersonaDefinition, ReviewResult | str]]:
    """Write the session's report and findings, and return them as the review's result."""
    payload_data, report_md = orchestrator.generate_consolidated_report(
        payloads, stage_flags=stage_flags
    )
    p_def = PERSONAS[Persona.DEVSECOPS]
    findings_list = _collect_review_findings(orchestrator, payloads, payload_data, stage_flags)
    raw_analyzers = getattr(orchestrator, "static_analyzers", None)
    analyzers_dict = raw_analyzers if isinstance(raw_analyzers, dict) else {}
    result = ReviewResult(
        findings=findings_list,
        report_markdown=report_md,
        static_analyzers=analyzers_dict,
        summary="",
    )
    return [(p_def, result)]


def _review_routed_files_only(
    orchestrator: ReviewPipelineOrchestrator,
    stage_flags: ReviewStageFlags | None,
) -> list[tuple[PersonaDefinition, ReviewResult | str]]:
    """A review whose every file is routed past the personas: the secret scan reads them, the
    report says what it found, and no model is called (#948)."""
    from devops_cli.lang import MESSAGES

    scanned = stage_flags is None or stage_flags.static_scan
    message = (
        MESSAGES.review.nothing_for_personas
        if scanned
        else MESSAGES.review.nothing_for_personas_unscanned
    )
    print_info(message.format(count=len(orchestrator.secret_scan_files)), prefix=False)
    payloads = orchestrator.scan_routed_files(stage_flags=stage_flags)
    return _report_review(orchestrator, payloads, stage_flags)


def _check_and_warn_perimeter_changes(
    target_type: str,
    changed_files: Sequence[str],
    *,
    base_revision: BaseRevision | None,
    target_dir: Path,
) -> None:
    """Warn when a branch or PR review changes a file a review.toml suppression covers (#1150).

    The suppressions are read where the diff starts, so the change cannot hide its own.
    """
    if target_type not in {"branch", "pr"} or not changed_files:
        return
    config = load_review_config(base_revision, find_repo_root(target_dir))
    covering = covering_suppressions(changed_files, load_review_suppressions(config))
    if covering:
        print_warning(format_covering_suppressions(covering), prefix=False)


def _execute_review_workflow(
    pages: list[str],
    title: str,
    summary_only: bool,
    clients: ReviewClients,
    *,
    target_dir: Path,
    target_type: Literal["branch", "pr", "path"] = "path",
    target_ref: str = ".",
    stage_flags: ReviewStageFlags | None = None,
    concurrency: int | None = None,
    parallel: bool = True,
    base_revision: BaseRevision | None = None,
    full_output: bool = False,
    routed_files: Sequence[str] = (),
    session_id: str | None = None,
    partial_context: bool = False,
) -> list[tuple[PersonaDefinition, ReviewResult | str]]:
    """Common review execution workflow for path, branch, and PR reviews.

    `base_revision` is where a branch or PR diff starts; pre-analysis records each changed
    Python file's symbol delta from it. A path review has none. When it is a local revision,
    the target's conventions are read there rather than from disk. `full_output` prints the
    whole report to the terminal rather than the findings that matter and a summary of the rest.

    The files kept off the pages still reach the secret scan: a path review names them in
    `routed_files`, and a branch or PR's are the changes in `base_revision` they match (#948).
    When no page is left, no model is called.
    """
    from devops_cli.ai.review.history import review_subject
    from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator
    from devops_cli.lang import MESSAGES

    if len(pages) > 1:
        spans_msg = MESSAGES.review.spans_pages.format(count=len(pages))
        print_info(f"[dim]{spans_msg}[/dim]", prefix=False)

    all_files = sorted(list({fn for page in pages for fn in diff_file_names(page)}))
    if base_revision is not None and base_revision.changes:
        deleted = {c.path for c in base_revision.changes if c.change_type == "deleted"}
        all_files = [f for f in all_files if f not in deleted]

    if summary_only:
        print_info(f"[dim]{MESSAGES.review.generating_metadata}[/dim]", prefix=False)
        try:
            repo_target = find_repo_root(target_dir)
        except Exception:
            repo_target = None
        analysis_metas = _load_file_analysis_metas(all_files, repo_root=repo_target)
        _print_analysis_metadata(analysis_metas, title)
        return []

    _check_and_warn_perimeter_changes(
        target_type, all_files, base_revision=base_revision, target_dir=target_dir
    )
    subject = review_subject(target_type, target_ref, pages)
    orchestrator = ReviewPipelineOrchestrator(
        session_id=session_id,
        llm_client=clients.analysis,
        target_dir=target_dir,
        concurrency=concurrency,
        parallel=parallel,
        subject=subject,
        full_output=full_output,
        secret_scan_files=sorted(
            {
                *routed_files,
                *_routed_changes(base_revision, path_classes=load_path_classes(base_revision)),
            }
        ),
        base_revision=base_revision,
        partial_context=partial_context,
    )
    if not all_files:
        return _review_routed_files_only(orchestrator, stage_flags)

    server_info = orchestrator.get_server_info()
    n_af = len(all_files)
    with trace_span(
        "review.session",
        attributes={
            "session_id": orchestrator.session_id,
            "target_type": target_type,
            "target_ref": target_ref,
            "file_count": n_af,
        },
    ):
        print_info(
            f"[bold cyan]Initializing review pipeline session '{orchestrator.session_id}' "
            f"for {n_af} file(s) via {server_info}...[/bold cyan]",
            prefix=False,
        )
        results = _run_profiled_session(
            orchestrator,
            all_files,
            target_dir,
            pages,
            target_type,
            target_ref,
            stage_flags,
            base_revision,
        )
        return results or []
