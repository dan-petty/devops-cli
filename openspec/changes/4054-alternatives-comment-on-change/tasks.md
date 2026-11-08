# Tasks

## 1. Post the comment of a check only for a first or a changed result

Kind: behavior

Reads: `src/devops_cli/roadmap/alternatives.py`, `tests/roadmap/test_roadmap_alternatives_one_write.py`. Changes: `src/devops_cli/roadmap/alternatives.py`, `tests/roadmap/test_roadmap_alternatives_recheck.py` (new).

- [ ] 1.1 Write `tests/roadmap/test_roadmap_alternatives_recheck.py`: a first check, a recheck with the same verdict and tool (no second comment, the date moves, one write), a changed verdict, a changed tool, and the count of checks
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [ ] 1.2 In `AlternativesWriter.settle`, compare the verdict and the tool of the check with `check.item.job_record`, and call `store.comment` only for a first check or a changed result. The marks, the block and the metrics stay for every check
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_alternatives_recheck.py tests/roadmap/test_roadmap_alternatives_one_write.py tests/roadmap/test_roadmap_alternatives.py`

## 2. Plan the comment of a check with its condition

Kind: behavior

Reads: `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_dry_runs.py`. Changes: `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_dry_runs.py`.

- [ ] 2.1 Add the test of the condition of the planned comment to `tests/roadmap/test_roadmap_dry_runs.py`
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [ ] 2.2 Add the condition `check_changed` to `plan_conditions`, and plan the comment of `alternatives_requests` with it
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_dry_runs.py`

## 3. Say that a recheck with the same result posts no comment

Kind: documents

Reads: `docs/roadmap/alternatives.md`, `src/devops_cli/lang/en/help.py`. Changes: `docs/roadmap/alternatives.md`, `src/devops_cli/lang/en/help.py`, `README.md`.

- [ ] 3.1 In `docs/roadmap/alternatives.md`, change "What a check writes": the comment is posted for a first check and for a changed verdict or tool, and a recheck with the same result writes the block and the record only. Change the help text of `devops roadmap alternatives` the same way, and regenerate `README.md` with `devops docs generate --sync-readme`
  - Verification: `$ uv run devops ci docs`

## Criteria

- Group 1: `uv run pytest tests/roadmap/test_roadmap_alternatives_recheck.py -k same_verdict` - a recheck with the same verdict and tool posts no second comment. It updates the date.
- Group 1: `uv run pytest tests/roadmap/test_roadmap_alternatives_recheck.py -k changed` - a recheck with a new verdict, or with a new tool, posts one comment.
- Group 1: `uv run pytest tests/roadmap/test_roadmap_alternatives_recheck.py -k first_check` - a first check, with no recorded verdict, posts its comment.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
