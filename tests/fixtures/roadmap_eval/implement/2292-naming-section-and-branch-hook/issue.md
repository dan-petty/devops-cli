### Problem Description

The project has no complete branch-name rule, and nothing checks one.

- `CONTRIBUTING.md` (section 4) lists four prefixes: `feat`, `fix`, `refactor` and `docs`, each with `<short-description>`. `docs/SDLC.md` states the rule two more times: `feat/<description>` in Phase 1, and `feat/<desc>`, `fix/<desc>`, `docs/<desc>` and `refactor/<desc>` in "Branch Governance & Hierarchy". The three texts differ.
- The `Semantic PR title` check and release-please accept 11 Conventional Commit types. A branch for `perf`, `test`, `build`, `ci`, `style`, `chore` or `revert` has no listed prefix.
- In practice a branch names its issue, as in `fix/2273-wait-otel-exporter-threads` and `perf/1725-pipeline-test-wait`, like the change folder `openspec/changes/<issue>-<slug>`. No document says so. The drift shows on `origin`: eight branches named `implement_issue_*`, and local branches such as `fix/pin-ty-redundant-cast` with no issue number.
- No hook and no CI check reads a branch name. `.pre-commit-config.yaml` refuses a commit only on `main`.
- No section lists the other naming rules in one place (change folders, decision records, labels, constants, metrics, tests, code). Some have a check and some have none, and an agent cannot tell which.

### Reproduction Steps

1. Run `git switch -c implement_issue_1 origin/main`, change a file and run `git commit`.
2. The commit succeeds. Read `CONTRIBUTING.md` section 4 and `docs/SDLC.md` for the rule that the branch breaks: no document names `<type>/<issue>-<slug>`.

### Expected vs Actual Behavior

- Expected: one document states the branch pattern and the other naming rules, each with the check that enforces it. A commit on a branch that breaks the pattern is refused with the pattern in the message.
- Actual: three texts state part of the rule, and a commit on any branch except `main` is accepted.

### Environment Diagnostics

`main` at a7dd605e. `pre-commit-hooks` v5.0.0, whose `no-commit-to-branch` hook accepts `--pattern`, a regular expression matched against the branch name.

### Proposed remedy

- A branch is `<type>/<issue>-<slug>`. `<type>` is one of the 11 Conventional Commit types, the same list as the pull request title. `<issue>` is the one issue the pull request closes. `<slug>` is lowercase words and digits joined by hyphens, the slug of the change folder. Branches that bots make on GitHub (`release-please--*`, `renovate/*`) are outside the rule.
- `CONTRIBUTING.md` states the rule once in a new "Naming" section, with a table: each artifact, its form, and the check that enforces it, or "no check". `docs/SDLC.md` links the section and no longer repeats the rule.
- The open tool `no-commit-to-branch` (`--pattern` with a negative lookahead) refuses a commit on a branch that does not match. No new code.
- A test runs the pattern of the hook on accepted and refused names, and checks that the types in the pattern are the types of the documentation.

### Acceptance criteria

- [ ] `CONTRIBUTING.md` states the branch pattern once, and `docs/SDLC.md` links it.
- [ ] The "Naming" table lists each naming rule with the check that enforces it, or says that none does.
- [ ] A commit on a branch that does not match is refused by the pre-commit hook, and a test checks the pattern.
- [ ] `AGENTS.md` routes "name a branch" to the "Naming" section.
