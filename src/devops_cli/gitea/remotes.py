"""Implementation of Gitea remotes management for repositories (#1090)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path, PurePosixPath

import typer

from devops_cli.config.settings import (
    Settings,
    dotted_set,
    get_gitea_token,
    load_settings,
    save_settings,
)
from devops_cli.core.cli import repo_label
from devops_cli.core.process import run_subprocess
from devops_cli.core.repo import get_repo_origin_name
from devops_cli.git.operations import iter_workspace_repos
from devops_cli.gitea.client import GiteaClient
from devops_cli.gitea.exceptions import GiteaAccessBlocked, GiteaError
from devops_cli.output import print_error, print_info, print_table


def resolve_repo_owner_name(repo_dir: Path, base_dir: Path) -> tuple[str, str]:
    """Resolve owner and name for a repository directory."""
    try:
        rel = repo_dir.resolve().relative_to(base_dir.resolve())
        parts = rel.parts
        if len(parts) == 2:
            return parts[0], parts[1]
    except ValueError:
        pass

    origin = get_repo_origin_name(repo_dir)
    if origin and "/" in origin:
        owner, name = origin.split("/", 1)
        return owner, name.removesuffix(".git")

    return "unknown", repo_dir.name


def read_default_branch(repo_dir: Path) -> str:
    """Read the clone's GitHub default branch from origin/HEAD."""
    res = run_subprocess(
        ["git", "-C", str(repo_dir), "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if res.returncode == 0 and res.stdout.strip():
        branch = res.stdout.strip().removeprefix("origin/").strip()
        if branch:
            return branch
    return "main"


def _ensure_remote_org(client: GiteaClient, owner: str, *, dry_run: bool) -> None:
    current_user = client.current_user()
    if owner != current_user.login:
        org_info = client.org(owner)
        if org_info is None and not dry_run:
            client.create_org(owner, visibility="private")


def _ensure_remote_repo(
    client: GiteaClient, owner: str, name: str, default_branch: str, *, dry_run: bool
) -> bool:
    repo_info = client.repo(owner, name)
    if repo_info is not None:
        return False
    if not dry_run:
        client.create_repo(
            owner,
            name,
            private=True,
            auto_init=False,
            default_branch=default_branch,
        )
    return True


def _ensure_remote_protections(
    client: GiteaClient,
    owner: str,
    name: str,
    default_branch: str,
    branches: Sequence[str],
    *,
    dry_run: bool,
) -> int:
    protections = client.branch_protections(owner, name)
    existing_rules = {p.rule_name for p in protections}
    patterns_to_protect = [default_branch]
    for pat in branches:
        if pat not in patterns_to_protect:
            patterns_to_protect.append(pat)

    protected_count = 0
    for idx, pat in enumerate(patterns_to_protect):
        if pat not in existing_rules:
            if not dry_run:
                client.create_branch_protection(
                    owner,
                    name,
                    rule_name=pat,
                    enable_push=True,
                    enable_force_push=False,
                    priority=idx,
                )
            protected_count += 1
    return protected_count


def _ensure_remote_git_config(
    repo_dir: Path, target_url: str, gitea_url: str, *, dry_run: bool
) -> str:
    remotes_res = run_subprocess(
        ["git", "-C", str(repo_dir), "remote", "-v"],
        check=False,
        capture_output=True,
        text=True,
    )
    remotes_lines = [line.split()[0] for line in remotes_res.stdout.splitlines() if line.strip()]
    if "gitea" not in remotes_lines:
        if not dry_run:
            run_subprocess(
                ["git", "-C", str(repo_dir), "remote", "add", "gitea", target_url], check=True
            )
        remote_action = "added"
    else:
        url_res = run_subprocess(
            ["git", "-C", str(repo_dir), "remote", "get-url", "gitea"],
            check=False,
            capture_output=True,
            text=True,
        )
        if url_res.stdout.strip() != target_url:
            if not dry_run:
                run_subprocess(
                    ["git", "-C", str(repo_dir), "remote", "set-url", "gitea", target_url],
                    check=True,
                )
            remote_action = "updated"
        else:
            remote_action = "ok"

    if not dry_run:
        run_subprocess(
            ["git", "-C", str(repo_dir), "config", "--add", f"credential.{gitea_url}.helper", ""],
            check=False,
        )
        run_subprocess(
            [
                "git",
                "-C",
                str(repo_dir),
                "config",
                "--add",
                f"credential.{gitea_url}.helper",
                "!devops repos gitea credential",
            ],
            check=False,
        )
        run_subprocess(
            ["git", "-C", str(repo_dir), "config", "checkout.defaultRemote", "origin"],
            check=False,
        )
        run_subprocess(
            ["git", "-C", str(repo_dir), "config", "remote.gitea.tagOpt", "--no-tags"],
            check=False,
        )
    return remote_action


def _seed_remote_default_branch(repo_dir: Path, default_branch: str, *, dry_run: bool) -> bool:
    if dry_run:
        return True
    push_res = run_subprocess(
        [
            "git",
            "-C",
            str(repo_dir),
            "push",
            "gitea",
            f"refs/remotes/origin/{default_branch}:refs/heads/{default_branch}",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    return push_res.returncode == 0


def ensure_clone_remotes(
    repo_dir: Path,
    base_dir: Path,
    client: GiteaClient,
    settings: Settings,
    *,
    dry_run: bool = False,
) -> tuple[bool, int, str, bool]:
    """Ensure Gitea repository, protection, remote URL, helper, and default branch seed."""
    owner, name = resolve_repo_owner_name(repo_dir, base_dir)
    default_branch = read_default_branch(repo_dir)

    _ensure_remote_org(client, owner, dry_run=dry_run)
    created_repo = _ensure_remote_repo(client, owner, name, default_branch, dry_run=dry_run)
    protected_count = _ensure_remote_protections(
        client, owner, name, default_branch, settings.gitea.github_branches, dry_run=dry_run
    )
    target_url = f"{settings.gitea.url}/{owner}/{name}.git"
    gitea_url = settings.gitea.url or ""
    remote_action = _ensure_remote_git_config(repo_dir, target_url, gitea_url, dry_run=dry_run)
    seeded = _seed_remote_default_branch(repo_dir, default_branch, dry_run=dry_run)

    return created_repo, protected_count, remote_action, seeded


def _collect_remotes_repos(
    root: Path,
    extra_paths: list[Path] | None,
    settings: Settings,
    *,
    dry_run: bool,
) -> list[Path]:
    if extra_paths:
        updated = False
        for p in extra_paths:
            resolved_str = str(p.resolve())
            if resolved_str not in settings.gitea.extra_checkouts:
                settings.gitea.extra_checkouts.append(resolved_str)
                updated = True
        if updated and not dry_run:
            dotted_set(settings, "gitea.extra_checkouts", settings.gitea.extra_checkouts)
            save_settings(settings, keys=("gitea.extra_checkouts",))

    repos: list[Path] = list(iter_workspace_repos(root))
    for ep_str in settings.gitea.extra_checkouts:
        ep = Path(ep_str)
        if ep.exists() and ep not in repos:
            repos.append(ep)
    return repos


def _process_remotes_clone(
    repo_dir: Path,
    root: Path,
    client: GiteaClient,
    settings: Settings,
    *,
    dry_run: bool,
) -> list[str]:
    created, protected, remote_action, seeded = ensure_clone_remotes(
        repo_dir,
        root,
        client,
        settings,
        dry_run=dry_run,
    )
    return [
        repo_label(repo_dir),
        "yes" if created else "-",
        str(protected) if protected > 0 else "-",
        remote_action,
        "yes" if seeded else "-",
    ]


def run_repos_remotes(
    base_dir: Path | None = None,
    extra_paths: list[Path] | None = None,
    *,
    dry_run: bool = False,
) -> None:
    """Run devops repos remotes command across workspace clones."""
    settings = load_settings()
    if not settings.gitea.url:
        print_error(
            "Gitea URL is not configured. Run 'devops repos gitea connect'.",
            prefix=False,
        )
        raise typer.Exit(1)

    token = get_gitea_token(settings)
    if not token:
        print_error(
            "Gitea token is not set. Run 'devops config set gitea.token'.",
            prefix=False,
        )
        raise typer.Exit(1)

    root = (base_dir or settings.repos.base_dir).resolve()
    repos = _collect_remotes_repos(root, extra_paths, settings, dry_run=dry_run)

    rows: list[list[str]] = []
    has_errors = False

    with GiteaClient(settings.gitea.url, token) as client:
        for repo_dir in repos:
            if repo_dir.parent.name == "_standalone":
                print_info(f"Skipping standalone clone {repo_label(repo_dir)}", prefix=False)
                continue
            try:
                rows.append(
                    _process_remotes_clone(repo_dir, root, client, settings, dry_run=dry_run)
                )
            except GiteaAccessBlocked as exc:
                print_error(str(exc), prefix=False)
                raise typer.Exit(1) from exc
            except GiteaError as exc:
                has_errors = True
                print_error(f"{repo_label(repo_dir)}: {exc}", prefix=False)
                rows.append([repo_label(repo_dir), "error", "-", "-", "-"])

    if rows:
        print_table("Gitea remotes", ["clone", "created", "protected", "remote", "seeded"], rows)

    if has_errors:
        raise typer.Exit(1)


def _extract_branch_name_from_porcelain(line: str, fallback_branches: list[str]) -> str:
    parts = line.split("\t")
    if len(parts) >= 2:
        ref_part = parts[1].strip()
        if ":" in ref_part:
            dst = ref_part.split(":", 1)[1]
            return dst.removeprefix("refs/heads/").strip()
        return ref_part.removeprefix("refs/heads/").strip()
    tokens = line.split()
    if len(tokens) >= 2:
        token = tokens[1].strip()
        if ":" in token:
            dst = token.split(":", 1)[1]
            return dst.removeprefix("refs/heads/").strip()
        return token.removeprefix("refs/heads/").strip()
    return fallback_branches[0] if fallback_branches else "main"


def _collect_branches_to_sync(
    repo_dir: Path, default_branch: str, patterns: Sequence[str]
) -> list[str]:
    refs_res = run_subprocess(
        [
            "git",
            "-C",
            str(repo_dir),
            "for-each-ref",
            "--format=%(refname:strip=3)",
            "refs/remotes/origin",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    candidates: list[str] = []
    if refs_res.returncode == 0:
        candidates = [
            line.strip()
            for line in refs_res.stdout.splitlines()
            if line.strip() and line.strip() != "HEAD"
        ]
    if default_branch and default_branch not in candidates:
        candidates.append(default_branch)

    matched: list[str] = []
    for branch in candidates:
        if branch == default_branch:
            if branch not in matched:
                matched.append(branch)
            continue
        if any(PurePosixPath(branch).full_match(pat) for pat in patterns):
            if branch not in matched:
                matched.append(branch)
    return matched


def _process_porcelain_lines(output: str, label: str, branches: list[str]) -> tuple[bool, bool]:
    success = True
    has_porcelain = False
    for raw_line in output.splitlines():
        if not raw_line or raw_line.startswith("To ") or raw_line == "Done":
            continue
        flag = raw_line[0] if raw_line else ""
        if flag in ("*", " ", "+"):
            has_porcelain = True
            b_name = _extract_branch_name_from_porcelain(raw_line, branches)
            print_info(f"{label}: {b_name} updated", prefix=False)
        elif flag == "!":
            has_porcelain = True
            b_name = _extract_branch_name_from_porcelain(raw_line, branches)
            print_error(
                f"{label}: {b_name} rejected (non-fast-forward). "
                f"Inspect with: git log gitea/{b_name} ^origin/{b_name}",
                prefix=False,
            )
            success = False
        elif flag == "=":
            has_porcelain = True
    return success, has_porcelain


def sync_repo_to_gitea(repo_dir: Path, label: str, settings: Settings) -> bool:
    """Push GitHub default branch and matching configured branches to Gitea."""
    remotes_res = run_subprocess(
        ["git", "-C", str(repo_dir), "remote"],
        check=False,
        capture_output=True,
        text=True,
    )
    remotes = [line.strip() for line in remotes_res.stdout.splitlines() if line.strip()]
    if "gitea" not in remotes:
        return True

    default_branch = read_default_branch(repo_dir)
    branches = _collect_branches_to_sync(repo_dir, default_branch, settings.gitea.github_branches)
    if not branches:
        return True

    cmd = ["git", "-C", str(repo_dir), "push", "--porcelain", "gitea"] + [
        f"refs/remotes/origin/{b}:refs/heads/{b}" for b in branches
    ]
    push_res = run_subprocess(cmd, check=False, capture_output=True, text=True)
    success, has_porcelain = _process_porcelain_lines(push_res.stdout, label, branches)

    if push_res.returncode != 0 and not has_porcelain:
        err_msg = push_res.stderr.strip() or push_res.stdout.strip()
        print_error(f"{label}: git push gitea failed: {err_msg}", prefix=False)
        return False

    return success
