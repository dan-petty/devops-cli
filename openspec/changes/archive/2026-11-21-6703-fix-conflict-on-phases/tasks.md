# Tasks

## 1. fix-conflict on the phases (behavior)

- [x] 1.1 Write the failing tests: a `reference-transaction` hook that tier 1 writes does not change a pushed round; the three phases on one run folder settle and push with no GitHub call in the agent phase; each phase hardens its process first and checks its runner; a phase needs `--work`.
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_step_fix_conflict.py tests/commands/test_roadmap_step_fix_conflict.py`
- [x] 1.2 Add `fix_conflict_phases.py` and `--phase` and `--work`, move the admission to `admit_round`, and delete the clone, fetch, push and tier 1 code of `fix_conflict.py` and `fix_rebase_conflict`.
  - Verification: `$ uv run devops ci test tests/roadmap/steps tests/commands/test_roadmap_step_fix_conflict.py`
- [x] 1.3 Write the failing tests, then fix: a timeout of tier 1 and a head that moves before the push count the round, which `prepare` records; the stop of a failed program holds its output; a plan on a host with no App gives `planned`.
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_step_fix_conflict.py`

## 2. The shared rebase and archive code (refactor)

- [x] 2.1 Add `archive_change` to `roadmap/phases/rebase.py`, and call it from fix-checks, fix-conflict and the archive step of implement. Stop the shared loop on a refused `--skip` or `--continue`, and take only the archive commit of the item.
  - Verification: `$ uv run devops ci test tests/roadmap/implement tests/roadmap/steps tests/roadmap/phases`
- [x] 2.2 Delete the fetch of `OriginGit` and the write-back of the `shallow` file, which have no caller now.
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_git_isolation.py`

## 3. Documents

- [x] 3.1 Describe the phases in `SECURITY.md` and the module texts, regenerate the command reference, and change the spec `roadmap-fix-conflict`.
  - Verification: `$ uv run devops ci --check --only docs,openspec`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
