# Task 843: GitHub CI Runs the Gate Through devops ci

**Issue**: [#843](https://github.com/dan-petty/devops-cli/issues/843)
**Status**: Done
**Milestone**: `v0.2.26`
**Priority**: `priority/p1-high`
**Scope**: `type/refactor`, `scope/cli`, `priority/p1-high`

---

## 1. Description & Objectives

Drift between GitHub CI and the local gate (`uv run devops ci`) previously caused divergence in check command arguments, bandit severity rules, and devcontainer validation. This item unifies check definitions into a single ordered table of check specifications in `commands/ci.py`, makes subcommands run their table row, adds `--only` and `--skip` filtering to the aggregate gate callback, aligns Bandit scanning to `-ll` across the codebase with specific `# nosec B608` suppressions, updates `.github/workflows/ci.yml` so that CI jobs run `devops ci` commands, removes the redundant `--xml` flag from `devops ci coverage`, and introduces offline parity tests asserting parity between `ci.yml` and the check table.

#### Key Deliverables:
- Single source of truth: Ordered table of check specifications in `src/devops_cli/commands/ci.py` defining check and fix argvs across `test`, `lint`, `format`, `typecheck`, `audit`, `security`, `actionlint`, `docs`, `uv-check`, `lockfile`, `outdated`, and `devcontainer`.
- Unified check options: `--only` and `--skip` options on `devops ci` with mutual exclusivity and invalid name rejection. Single-row executions stream stdout directly (`capture_output=False`), preserving live output.
- Bounded execution & error handling: `TimeoutExpired` exceptions in async check execution turn into structured failure results recording check names and timeout limits.
- Subcommand parity: `devops ci` subcommands dispatch directly through the check specification table.
- Bandit unification: Standardized on `-ll` everywhere; removed blanket `-s B608` skips; applied targeted `# nosec B608` annotations in `instruction_generator.py` and `stack_lifecycle.py`; removed unused `build_bandit_cmd`.
- Workflow parity: `.github/workflows/ci.yml` updated so `static` runs `devops ci --check --no-cache --skip test,outdated`, `test` runs `devops ci --check --no-cache --only test`, and `dependency-freshness` runs `devops ci outdated`.
- Parity test suite: `tests/test_ci.py` asserts structural parity between `ci.yml` run steps and the check specification table, pinning job names `Static Analysis` and `Tests & Coverage`.
- CLI documentation regenerated without `--xml` option on `devops ci coverage`.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).

---

## 2. Acceptance Criteria Checklist

- [x] **Check specification table**: Single ordered table of check specs in `commands/ci.py` feeding aggregate gate, subcommands, and CI jobs.
- [x] **Bandit rule set**: Security row standardized to `uv run bandit -r src -ll`; scanner adapters drop `-s B608`; targeted `# nosec B608` placed on `instruction_generator.py` and `stack_lifecycle.py`; `build_bandit_cmd` and `DEFAULT_BANDIT_EXCLUDE` removed.
- [x] **Workflow alignment**: `ci.yml` static, test, and dependency-freshness jobs call `devops ci`.
- [x] **Parity test**: Offline PyYAML validation in `tests/test_ci.py` asserts `ci.yml` steps invoke `devops ci` reaching all rows, with mutation tests ensuring invalid configurations fail.
- [x] **Selection**: `devops ci --only` and `--skip` tested via CliRunner for valid dispatch and error handling on invalid names or conflicting options.
- [x] **Subcommand dispatch**: Subcommands execute identical check and fix argvs as their table rows.
- [x] **Fix execution order**: Fix mode runs formatting, linting, and docs tasks in correct sequence.
- [x] **Timeout handling**: `TimeoutExpired` converts to failed check result naming the check and timeout limit.
- [x] **Cache isolation**: Narrowed runs (`--only` / `--skip`) neither read nor populate the gate cache.
- [x] **Coverage XML**: Redundant `--xml` flag removed from `devops ci coverage`; coverage row writes `.data/coverage.xml`.
- Pending a person: `rm -f .data/coverage.xml && uv run devops ci --check --no-cache --only test && test -s .data/coverage.xml`
- [x] **Changelog fragment**: `changelog.d/843.md` records single-source CI gate definitions and workflow alignment.
