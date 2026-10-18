## Summary
<!-- What this pull request changes, and why. -->

---

## Type of Change
<!-- Mark the one that applies with an 'x'. -->
- [ ] `feat`: New feature or capability
- [ ] `fix`: Bug fix or defect remediation
- [ ] `refactor`: Code reorganization with zero functional behavior change
- [ ] `docs`: Documentation updates or additions
- [ ] `test`: New or updated tests
- [ ] `chore`: Maintenance, dependencies, or tooling updates

---

## Base Branch
<!-- Every pull request except the release pull request (`release/v<version>` into `main`), which carries the release branch as it stands, targets the active release branch. Two release-process pull requests into it close no issue: the cut pull request (`chore/cut-v<version>`), which only modifies the cut's files (`pyproject.toml`, `src/devops_cli/__init__.py`, `uv.lock`, `CHANGELOG.md`, `docs/ROADMAP.md`) and removes the fragments it collects, and the merge of `main` (`chore/open-v<version>-main`), which changes only the cut's files and what `main` changed since its merge base with the release branch. `devops pr check-readiness` holds either one to the Item section below when it changes any other file. -->
- `release/v<version>` (not `main`)

---

## Item
<!-- Name the one issue this pull request delivers and the task file it adds or changes. `devops pr check-readiness` blocks a pull request whose body closes no issue or several, or that does not change that issue's task file. An item planned as several pull requests says `Part of #<issue>` instead in each but the last, which closes it; until then its task file may read `**Status**: In Progress`. -->
Closes #<issue>

Task file: `docs/agent/tasks/task-<issue>-<slug>.md`

Changelog fragment: `changelog.d/<issue>.md`
<!-- The entry goes there. Do not edit `CHANGELOG.md` or `docs/ROADMAP.md`: the cut writes both, and `devops pr check-readiness` blocks a pull request into a release branch that changes either. A critical fix after the cut edits the version's `CHANGELOG.md` section instead, with no fragment. A `Part of #<issue>` pull request adds no fragment: the one that closes the item adds it. -->
