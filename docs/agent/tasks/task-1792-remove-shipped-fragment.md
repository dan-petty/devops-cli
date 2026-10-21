# Task: The v0.2.37 Changelog Fragment for #1723 Is Deleted, So the v0.2.38 Cut Does Not Publish It Again (#1792)

**Issue**: [#1792](https://github.com/dan-petty/devops-cli/issues/1792)
**Scope**: scope/release
**Feasibility**: `git log -- changelog.d/1723.md` on `release/v0.2.38` shows one commit, 954914e, the v0.2.37 release commit, which added the file. CHANGELOG [0.2.37] holds #1723's entry once. The cut collects every file under `changelog.d/`, so a fragment left there is collected again.

## Description

- [x] `changelog.d/1723.md` is deleted. `CHANGELOG.md` is unchanged.
