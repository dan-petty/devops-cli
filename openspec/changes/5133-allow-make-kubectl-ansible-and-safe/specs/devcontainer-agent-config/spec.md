## ADDED Requirements

### Requirement: The Claude Code settings allow the standard project commands
The `permissions.allow` list of `.claude/settings.json` and of its template SHALL allow `make`, `kubectl`, the Ansible commands, `uv sync`, `uv lock`, the git reads and the local git writes `worktree`, `add`, `commit` and `rebase`. It SHALL NOT allow `git push`, `git reset`, `git checkout`, `git switch` or `git stash`. The `permissions.deny` list SHALL keep `--no-verify` and bare `gh` refused.

#### Scenario: The scaffold writes the Claude settings
- **WHEN** a test runs `devops devcontainer init` in an empty directory
- **THEN** the `permissions.allow` list of `.claude/settings.json` is `Bash(uv run devops *)`, `Bash(uv run pytest *)`, `Bash(uv sync*)`, `Bash(uv lock*)`, `Bash(openspec *)`, `Bash(tuicr *)`, `Bash(make *)`, `Bash(kubectl *)`, `Bash(ansible *)`, `Bash(ansible-playbook *)`, `Bash(ansible-inventory *)`, `Bash(ansible-lint *)`, `Bash(git status*)`, `Bash(git diff*)`, `Bash(git log*)`, `Bash(git branch*)`, `Bash(git fetch*)`, `Bash(git show*)`, `Bash(git rev-parse*)`, `Bash(git merge-base*)`, `Bash(git worktree *)`, `Bash(git add *)`, `Bash(git commit *)` and `Bash(git rebase *)`
- **AND** the `permissions.deny` list is `Bash(git push * --no-verify*)`, `Bash(git commit * --no-verify*)` and `Bash(gh *)`
