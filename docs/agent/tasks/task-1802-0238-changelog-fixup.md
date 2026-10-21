# Task: The v0.2.38 Changelog Fragments Are Deleted and #1800's Entry Joins CHANGELOG [0.2.38] (#1802)

**Issue**: [#1802](https://github.com/dan-petty/devops-cli/issues/1802)
**Scope**: scope/release
**Feasibility**: `git ls-tree origin/main changelog.d/` at f92399ec lists 34 fragments and the README. The v0.2.38 release pull request (#1799) merged into `main`, then the cut pull request (#1798) merged on top as a second commit that changed CHANGELOG.md, docs/ROADMAP.md, pyproject.toml and uv.lock but deleted no fragment. CHANGELOG [0.2.38] holds the entries of the other 33 fragments, and none for #1800, whose fragment arrived after the cut was built.

## Description

- [x] The 34 fragments under `changelog.d/` are deleted, leaving the README, so the v0.2.39 cut does not collect them again.
- [x] CHANGELOG [0.2.38] holds #1800's `### Security` entry, once.
