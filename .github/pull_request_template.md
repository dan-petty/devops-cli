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
<!-- Every pull request except the release pull request targets the active release branch. A release-process pull request, which opens or cuts the release, comes from `chore/open-v<version>` or `chore/cut-v<version>`. -->
- `release/v<version>` (not `main`)

---

## Item
<!-- Name the one issue this pull request delivers and the task file it adds or changes. `devops pr check-readiness` blocks a pull request whose body closes no issue or several, or that does not change that issue's task file. -->
Closes #<issue>

Task file: `docs/agent/tasks/task-<issue>-<slug>.md`

Changelog fragment: `changelog.d/<issue>.md`
<!-- The entry goes there. Do not edit `CHANGELOG.md` or `docs/ROADMAP.md`: the cut writes both, and `devops pr check-readiness` blocks a pull request into a release branch that changes either. -->
