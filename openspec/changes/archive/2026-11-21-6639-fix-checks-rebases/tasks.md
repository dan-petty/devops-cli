# Tasks

## 1. The rebase of fix-checks (behavior)

- [x] 1.1 Write the failing tests with real git: a round on a branch behind main rebases, fixes the check and pushes with a lease on the judged head; the archive stays its own commit; a rebase conflict that no rule settles stops and pushes nothing; a lease that moved after the rebase stops with `head_moved`; a skipped archive commit is archived again; a failed `uv lock` aborts the rebase; two stops on a generated document are each settled; a rebase that git refuses to start stops.
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_step_fix_checks_repair.py`
- [x] 1.2 Move the rebase and settle rules of implement to `roadmap/phases/rebase.py`, call them from implement and from the agent phase of fix-checks, record `onto` in `prepare`, write the patches from `onto`, and publish them on it.
  - Verification: `$ uv run devops ci test tests/roadmap/steps tests/roadmap/implement tests/roadmap/phases`

## 2. The main-skew stop (refactor)

- [x] 2.1 Delete `BranchChange.main_paths`, its diff, its rule in `judge_scope` and its two tests.
  - Verification: `$ ! git grep -n -E "main_paths|main skew" src/ tests/`

## 3. Documents

- [x] 3.1 Describe the rebase in `docs/CLUSTER.md`, ADR 0030 and `docs/roadmap/package-layout.md`, and change the spec `roadmap-fix-checks`.
  - Verification: `$ uv run devops ci --check --only docs,openspec`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
