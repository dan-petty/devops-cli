# Design: Declare scope/git in labels.yml

## Context
Conventional commit titles can use the scope `git` (such as `test(git): ...` or `feat(git): ...`).
The `devops pr create` command matches the scope from the title against declared labels in `.github/labels.yml`.
When a scope has no entry in `.github/labels.yml`, `devops pr create` skips adding the scope label and warns the user.

## Design Decisions
- Add `scope/git` directly after `scope/github` in `.github/labels.yml`.
- Re-use the color `24292E` to match `scope/github`.
- Description: `Git commands, git configuration, and git credential handling`.
- Test that `.github/labels.yml` declares `scope/git` and that `devops pr create` attaches `scope/git` without warning.
