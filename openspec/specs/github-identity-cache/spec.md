# github-identity-cache Specification

## Purpose
Resolve and store the GitHub identity quota ledger and response cache in the platform user cache directory, keeping cache files out of working repositories.

## Requirements

### Requirement: Identity cache root outside the repository
The identity cache root SHALL resolve under the user cache directory that `platformdirs.user_cache_dir` returns for the application, not under the working repository.

#### Scenario: Path resolution from a temporary Git repository
- **WHEN** a test sets the working directory to a temporary Git repository and calls `resolve_identity_cache_dir` with a fixed identity
- **THEN** the returned path is not inside the temporary repository and has the `platformdirs` user cache directory as a parent.

### Requirement: Identity-scoped quota path
The quota ledger path SHALL keep the identity digest directory under the user cache root.

#### Scenario: Quota ledger path for one identity
- **WHEN** a test fixes the session identity and calls `resolve_quota_cache_path`
- **THEN** the path parent is `resolve_identity_cache_dir` for that identity and the file name is `gh_quota.json`.

### Requirement: No cache file in the working repository
A `devops gh api rate_limit` run SHALL write no quota ledger, lock file, or response cache file under the working repository.

#### Scenario: Rate-limit command in a temporary Git repository
- **WHEN** a test runs the rate-limit command with a stubbed GitHub response and the working directory in a temporary Git repository that has no `.data/` ignore rule
- **THEN** `git status --porcelain` reports no new file for the quota ledger, lock file, or response cache.
