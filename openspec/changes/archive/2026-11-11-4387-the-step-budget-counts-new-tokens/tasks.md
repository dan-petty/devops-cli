# Tasks

## 1. The budgets count the new tokens of a reply

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/implement_limits.py`, `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/roadmap/implement/implement_run.py`. Changes: `tests/support/model_script.py`, `tests/roadmap/implement/test_roadmap_implement_limits.py`, `tests/roadmap/implement/test_roadmap_implement_phase_marks.py`, `src/devops_cli/roadmap/implement/implement_limits.py`, `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/roadmap/implement/implement_run.py`.

- [x] 1.1 Give `ModelScript` the `cached` input tokens of each streamed reply. Add the tests of the count of one reply, of a step whose replies the cache served, and of the record of an earlier Job with cached input. Run them and see them fail
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_limits.py tests/roadmap/implement/test_roadmap_implement_phase_marks.py` fails on the base
- [x] 1.2 Add `new_tokens` and count it in `limit_hooks` and in the item spend. Keep `cache_read_tokens` in the outcome of a step, the spend of each tier and the record `implement.spend`, and the count of the item budget as `new_tokens` in the record. A record with no `new_tokens` counts none
  - Verification: `$ uv run devops ci test tests/roadmap/implement/` passes

## 2. The defaults and the texts of the new unit

Kind: behavior. Reads: `src/devops_cli/config/defaults.py`. Changes: `tests/roadmap/implement/test_roadmap_implement_limits.py`, `tests/roadmap/implement/test_roadmap_implement_extension.py`, `tests/roadmap/implement/test_roadmap_implement_job_extension.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/lang/en/messages.py`.

- [x] 2.1 Expect "new tokens" in the reasons and the extension lines, and a default step budget that gives a step on a route with no cache reads about 200 requests of 39300 input tokens. Run the tests and see them fail
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_limits.py tests/roadmap/implement/test_roadmap_implement_extension.py tests/roadmap/implement/test_roadmap_implement_job_extension.py` fails on the base
- [x] 2.2 Keep the default values, and set the descriptions of the three settings and the texts of the stop and of the extension
  - Verification: `$ uv run devops ci test tests/roadmap/implement/ tests/roadmap/test_roadmap_limit_classes.py` passes

## 3. Documents

Kind: other. Reads: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/implement.md`. Changes: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/implement.md`, `docs/ENV_VARS.md`.

- [x] 3.1 State the unit, the defaults and the record in `docs/ROADMAP_WORKFLOW.md` and `docs/roadmap/implement.md`, and regenerate the documents
  - Verification: `$ uv run devops docs generate --sync-readme` leaves no further diff

## Workflow follow-up

- Pending a person: delete `roadmap.implement.step_token_budget` from the live ConfigMap `devops/devops-cli-config` after the image with this change runs.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
