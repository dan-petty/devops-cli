# Proposal: #6529

## Why
`devops gh` writes its quota ledger and response cache under the repository of the working directory (`.data/cache/<identity>/gh_quota.json`). When a clone does not ignore `.data/`, git status shows these files as untracked files. A builder committed quota files into a repository clone (#6529, `devtools#14`). The quota ledger belongs to the identity, not to a repository. Two repositories that share one identity keep two separate ledgers.

## What Changes
- Move the identity cache root from `data.cache_dir` in the working repository to the user cache directory from `platformdirs.user_cache_dir("devops-cli")`.
- Keep the SHA-256 identity digest directory and `gh_quota.json` file layout under the user cache directory.
- Verify that `devops gh api rate_limit` in a clean Git clone writes no file into that clone.

## Capabilities
- Resolves GitHub identity cache outside the working repository.
- Prevents quota ledger and response cache files from polluting git status in clones.

## Impact
- Quota ledger and response cache persist across repositories for each user identity.
- No change to CLI command syntax or flags.

## Feasibility
- `platformdirs.user_cache_dir("devops-cli")` resolves to the platform user cache directory (for example, `~/.cache/devops-cli` on Linux).
- Tests prove that running `devops gh api rate_limit` in a repository leaves `git status --porcelain` empty.

## Existing Tool Considered
`platformdirs` is already in use by the repository for platform directory resolution. The change uses `platformdirs.user_cache_dir(CONST_APP_NAME)` for the identity cache root.
