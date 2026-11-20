# Design

## Decisions
- The rule is in the shared preset, so each repository that extends it gets it. The owner asked for all minor and bug-fix updates.
- `platformAutomerge: false`: Renovate itself checks each check of the pull request before it merges. GitHub auto-merge would wait only for the checks of a ruleset, and a repository with no required check would merge at once.
- `digest` is in the rule. The groups `github actions` and `container images` hold digest updates, and a group branch merges only when each update in it can merge. A digest update is a new build of the same tag.
- `automergeType: pr`: each update keeps its pull request, so the history and the release notes name it.

## Rejected alternatives
- GitHub auto-merge with a ruleset in each repository: the owner changes repository settings, and two repositories have no required check today.
- Only `minor` and `patch`: no group with a digest update would merge.
- Lock file maintenance in the rule: it can take a new major of a transitive dependency when the range of its parent allows that major.
