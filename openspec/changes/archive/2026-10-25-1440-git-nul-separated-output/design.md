# Design

## Context

See `proposal.md` for problem motivation and scope.

Git commands emit listings in human format by default. Human format C-quotes characters outside 7-bit US-ASCII and whitespace characters. It prints renames as `old -> new`.

Several modules parse these listings with line splitting and quote stripping. This causes path corruption, loss of leading characters, and silent drops.

## Goals / Non-Goals

**Goals:**
- Read git path listings with `-z` across `argo/gitops.py`, `core/repo.py`, `commands/test_cmd.py`, `roadmap/refine.py`, and `core/cleanup.py`.
- Correctly parse rename records in `git status --porcelain=v1 -z`.
- Resolve relative porcelain status paths against the repository root.
- Add tests in temporary git repositories verifying paths with spaces, non-ASCII characters, leading spaces, and renames.

**Non-Goals:**
- Change git commit, branch, or tag management.
- Modify release or PR commands that were already cleaned in #1952.
- Introduce external git wrapper libraries.

## Decisions

### 1. Tokenize `git status --porcelain=v1 -z` with two-path rename handling

In `argo/gitops.py`, run `git status --porcelain=v1 -z`. Split the output by `\0`.

When the two-letter status code contains `R` or `C`, git emits the new path followed by the old path as a separate null-terminated token. The parser consumes the original path token to keep synchronization with subsequent entries.

*Rejected Alternative*: Parse line-oriented `git status --porcelain` with regex unquoting.
*Evidence*: C-style unquoting does not reliably distinguish between literal escape characters and escaped octal bytes (such as `\303\251`). It also corrupts paths that contain ` -> `.

### 2. Resolve porcelain status paths against the repository root

`git status` outputs paths relative to the repository root. `inspect_git_manifest_drift` resolves relative paths using `(repo_root / rel_path).resolve()`.

*Rejected Alternative*: Resolve paths against `Path.cwd()`.
*Evidence*: When the process working directory is not the repository root, `Path(rel_path).resolve()` targets the wrong directory on disk.

### 3. Parse `git ls-files` and `git diff` with `-z`

In `core/repo.py` and `commands/test_cmd.py`, append `-z` to `ls-files` and `diff --name-only`. Split output on `\0`.

*Rejected Alternative*: Set `git config core.quotePath false`.
*Evidence*: Modifying git configuration alters persistent repository or global state, violating AGENTS.md rule 12.

### 4. Parse `git worktree list --porcelain -z`

In `core/cleanup.py`, run `git worktree list --porcelain -z` and split on `\0`. Extract records starting with `worktree `.

*Rejected Alternative*: Split on newline characters without `-z`.
*Evidence*: Worktree paths with spaces or unusual characters get misparsed or stripped.

## Risks / Trade-offs

- [Risk] Null-separated parsing can produce an empty string at the end of the split list.
  → Mitigation: Filter out empty tokens when splitting by `\0`.
- [Risk] Renamed manifests might leave the old file in persistent caches.
  → Mitigation: For renames, the new path is tracked as modified/created, and the old path is consumed so subsequent entries parse cleanly.
