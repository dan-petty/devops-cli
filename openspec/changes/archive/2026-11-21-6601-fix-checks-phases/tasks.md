# Tasks

## 1. The phases

Kind: behavior.

- [x] 1.1 Write failing tests: the read of an output as data; the patch in a new git folder; the publish of one commit of the bot, with the lease and the refusals of a link, a gitlink, `.gitmodules`, a `.git` path and a workflow file
  - Verification: `$ uv run devops ci test tests/roadmap/phases`
- [x] 1.2 Add `roadmap/phases` (`files.py`, `patch.py`, `publish.py`, `names.py`), and a depth to `OriginGit.fetch`
  - Verification: `$ uv run devops ci test tests/roadmap/phases tests/roadmap/implement/test_roadmap_implement_git_isolation.py`

## 2. fix-checks on the phases

Kind: behavior.

- [x] 2.1 Write failing tests: the three phases on a run folder; a round that `prepare` ends; the claim in `publish` and before the push; an outcome outside the enums; a fixer that rewrites the state file; a state file that is a link or not of its model; `prepare` with git only and no credential in its clone; the workflow files of the merged plan read by `publish`; the hardening first for each phase; the agent phase with no App key
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_step_fix_checks.py tests/roadmap/steps/test_roadmap_step_fix_checks_repair.py tests/commands/test_roadmap_step_fix_checks.py`
- [x] 2.2 Split `run_fix_checks` into `judge_round` and the phases (`fix_checks_phases.py`), move the checkout of `fix_checks_repair.py` into the work folder, and add `--phase` and `--work`
  - Verification: `$ uv run devops ci test tests/roadmap/steps tests/commands/test_roadmap_step_fix_checks.py`

## 3. Documents

Kind: other.

- [x] 3.1 Add ADR 0030 in status proposed, add `phases/` to `docs/roadmap/package-layout.md`, note the run folder in `docs/CLUSTER.md` and `k8s/devops/cronjob-runner.yaml`, and regenerate the documentation
  - Verification: `$ uv run devops ci docs`
