# Tasks

## 1. Count the continuations of an item

Kind: behavior. Reads: `src/devops_cli/config/defaults.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/roadmap/store.py`. Changes: `src/devops_cli/config/defaults.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/roadmap/store.py`, `tests/roadmap/test_roadmap_digest_clears.py`, `tests/roadmap/test_roadmap_limit_classes.py`, `tests/security/test_config_declarations.py`.

- [x] 1.1 Write tests: the setting defaults to 2, the variable `DEVOPS_CLI_ROADMAP_IMPLEMENT_CONTINUATIONS_PER_ITEM` sets it to 0, a negative count is refused, the default is classified as a setting, and the variable is declared
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_digest_clears.py tests/roadmap/test_roadmap_limit_classes.py tests/security/test_config_declarations.py` fails on the base
- [x] 1.2 Add `DEFAULT_ROADMAP_IMPLEMENT_CONTINUATIONS_PER_ITEM`, the field `continuations_per_item` and the record key `ImplementRecordKey.CONTINUATIONS`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_digest_clears.py tests/roadmap/test_roadmap_limit_classes.py tests/security/test_config_declarations.py` passes

## 2. Clear a stop `job` by the rule `continue`

Kind: behavior. Reads: `src/devops_cli/roadmap/stop_clear.py`, `src/devops_cli/roadmap/failure.py`. Changes: `src/devops_cli/roadmap/stop_clear.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stop_clear.py`, `tests/roadmap/test_roadmap_implement_project_steps.py`.

- [x] 2.1 Write tests: a stop `job` of each class with the action `retry` is continued whatever the digest, a class with another action and a stop with no class wait, a stop that the runner wrote is no continuation, the limit and the last comment, a limit of 0, a retry after the limit, no digest clear is spent, a count that is no count, and the report names the setting
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stop_clear.py tests/roadmap/test_roadmap_implement_project_steps.py` fails on the base
- [x] 2.2 Replace `DigestLimits` by `ClearLimits`, add the rule `continue` before the rule `digest`, add the messages `stop_clear_continue` and `stop_clear_continue_last`, and reword `implement_job_report_stopped`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stop_clear.py tests/roadmap/test_roadmap_implement_project_steps.py` passes

## 3. Continue a Job in the round of the row

Kind: behavior. Reads: `src/devops_cli/roadmap/implement_submit.py`, `tests/roadmap/test_roadmap_implement_submit.py`, `tests/roadmap/test_roadmap_implement_deadline.py`. Changes: `src/devops_cli/roadmap/implement_submit.py`, `src/devops_cli/roadmap/implement_run.py`, `tests/support/roadmap_implement.py`, `tests/roadmap/test_roadmap_implement_submit.py`, `tests/roadmap/test_roadmap_implement_deadline.py`.

- [x] 3.1 Add the fixture `no_continuation` and use it in the 13 tests of `test_roadmap_implement_submit.py` and the 2 tests of `test_roadmap_implement_deadline.py` that read the stop of a failed Job. Write round tests: continuation 1, continuation 2 with "No continuation is left", an item that stays Blocked, a Job that no longer exists, a log with an out-of-memory kill, a stop of the runner, a retry after the limit, and the digest budget
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_submit.py tests/roadmap/test_roadmap_implement_deadline.py` fails on the base
- [x] 3.2 Update the module docstrings of `implement_submit.py` and `implement_run.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_submit.py tests/roadmap/test_roadmap_implement_deadline.py` passes

## 4. Say how a Job with no result continues

Reads: `k8s/README.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/implement.md`, `docs/ROUTINE_TASKS.md`. Changes: `k8s/README.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/implement.md`, `docs/ROUTINE_TASKS.md`, `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`.

- [x] 4.1 Add the rule `continue`, the setting and the record key to step 16 of `k8s/README.md`, the table and the stop path of `docs/ROADMAP_WORKFLOW.md`, the stop paragraph of `docs/roadmap/implement.md` and `docs/ROUTINE_TASKS.md`, then run `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci docs` passes

## Criteria

- Group 1: A test: `roadmap.implement.continuations_per_item` is 2 by default and refuses a negative count.
- Group 2: A test: a stop `job` of the class `ci_infra` is cleared by the rule `continue`, `implement.continuations` is 1, and the comment says "continuation 1 of 2".
- Group 2: A test: after two continuations the item stays Blocked and the last comment says "No continuation is left".
- Group 2: A test: a stop of a class whose action is not `retry` is not continued.
- Group 3: A test: three Jobs that end with no result make two new Jobs, and no round makes a fourth.
- Group 3: A test: a log with an out-of-memory kill makes no new Job.

## Workflow follow-up

- #3062 keeps the checkpoint of each passed group. A group of one task runs again after a continuation until that checkpoint exists.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
