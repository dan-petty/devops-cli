# Task: The Project's Claude Code Settings Are Checked In, While Local Settings, Scratch and Worktrees Stay Ignored (#1087)

**Issue**: [#1087](https://github.com/dan-petty/devops-cli/issues/1087)
**Status**: Done
**Milestone**: v0.2.25
**Priority**: priority/p2-medium
**Scope**: scope/config

## Description
`.gitignore` ignored the whole `.claude/` directory, so the project's shared Claude Code settings (`.claude/settings.json`: enabled plugins and permission rules) were never in git. The rule now ignores `.claude/*` and re-includes `.claude/settings.json`, which is committed as it stands. Personal settings (`.claude/settings.local.json`), `.claude/scratch/` and `.claude/worktrees/` stay ignored.

## Acceptance Criteria
- [x] `.gitignore` ignores `.claude/*` and re-includes `.claude/settings.json`. `git check-ignore` reports `.claude/settings.local.json`, `.claude/scratch/x` and `.claude/worktrees/x` as ignored and `.claude/settings.json` as not ignored.
- [x] `.claude/settings.json` is committed as it stands; it holds no secret, token or host name.
- [x] A changelog fragment is added, and `uv run devops ci` passes.
