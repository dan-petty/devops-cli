# Tasks

## 1. Guard row 12 on the default webhook URL

Kind: behavior. Reads: `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/github/onboard/service_rows.py`, `tests/support/github_repository.py`, `tests/support/config.py`, `tests/commands/test_repos_onboard.py`, `tests/config/test_research_judge_limits.py`, `tests/config/test_settings.py`, `tests/github/onboard/test_onboard_routes.py`. Changes: `src/devops_cli/config/defaults.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/github/onboard/service_rows.py`, `tests/support/github_repository.py`, `tests/commands/test_repos_onboard.py`.
Adds: `DEFAULT_SERVICE_WEBHOOK_URL`, `webhook_url_step`

- [ ] 1.1 Write `test_a_default_webhook_url_is_a_person_step` and `test_a_confirm_with_the_default_webhook_url_writes_no_hook` in `tests/commands/test_repos_onboard.py` first: with `service.webhook_url` at its default, `devops repos onboard example-org/app --plan` gives row 12 the state `person` with a step that names `service.webhook_url` and no request to a hooks route, and `--confirm --only 12` records no POST and no PATCH there
  - Verification: `$ uv run devops ci test tests/commands/test_repos_onboard.py` fails on the base
- [ ] 1.2 Add `DEFAULT_SERVICE_WEBHOOK_URL: Final[str] = "https://hooks.example.com/webhooks/github"` to the Service section of `src/devops_cli/config/defaults.py`, and make the `webhook_url` field of `src/devops_cli/config/settings.py` default to it. Add `webhook_url_step()` to `src/devops_cli/github/onboard/service_rows.py` and, as the first branch of `webhook_row` before the hooks read, return the state `person` with that step when the setting equals the constant. Set `WEBHOOK_URL` in `tests/support/github_repository.py` to `https://webhooks.example.com/github`, so the existing tests keep a set URL, and write the two tests in `tests/commands/test_repos_onboard.py` that pass the default through the `config` fixture
  - Verification: `$ uv run devops ci test tests/commands/test_repos_onboard.py` passes

## 2. Write the webhook secret only in the run that deploys it

Kind: behavior. Reads: `src/devops_cli/github/onboard/service_rows.py`, `src/devops_cli/github/onboard/run.py`, `src/devops_cli/github/onboard/model.py`, `tests/github/onboard/test_onboard_rows.py`, `tests/github/onboard/conftest.py`, `tests/github/onboard/test_onboard_routes.py`, `tests/infra/test_onboard.py`. Changes: `src/devops_cli/github/onboard/service_rows.py`, `src/devops_cli/github/onboard/run.py`, `tests/github/onboard/test_onboard_rows.py`.
Adds: `DeployPlan`, `deploy_plan`, `webhook_secret_step`

- [ ] 2.1 Write `test_a_secret_write_needs_the_service_row`, `test_a_no_deploy_run_writes_no_hook_secret`, `test_a_refused_service_row_writes_no_hook_secret` and `test_the_service_row_writes_the_secret` in `tests/github/onboard/test_onboard_rows.py` first, and change `test_a_drifted_repository_gets_one_write_for_each_difference` to expect row 12 `pending`, row 13 `present`, no hook PATCH and no deploy-stack step: with a set URL and an existing hook whose secret the map lacks, a confirmed row 12 sends no PATCH when row 13 is out of `--only`, when `--no-deploy` is set, or when `git status` lists a file, and the run with row 13 in `--only` sends one PATCH that carries the new secret
  - Verification: `$ uv run devops ci test tests/github/onboard/test_onboard_rows.py` fails on the base
- [ ] 2.2 Add `DeployPlan` and `deploy_plan(settings, ctx, *, wanted)` to `src/devops_cli/github/onboard/service_rows.py`, and list both in `__all__`: with `--confirm` and row 13 wanted it reads `clean_main_reason` once and, when that reason is None and the run deploys, `_deploy_tree` once, and it holds the reason and the tree; `deploy` is false when row 13 is not wanted, when `--no-deploy` is set, or when a reason is not None. Add `webhook_secret_step(repo, reason)` and give `webhook_row` the keyword-only `deploy: DeployPlan`; in the branch of an existing hook that needs a new secret, return `pending` with that step, write nothing and set no `ctx.service_changed` when the plan does not deploy. Give `service_row` the plan in place of its own `clean_main_reason` and `_deploy_tree` calls. In `src/devops_cli/github/onboard/run.py`, read the plan once before row 12 when no earlier row stopped the run, and give it to both rows. Update the write list and the row-13 assertions of the drift test, and add the four tests
  - Verification: `$ uv run devops ci test tests/github/onboard/test_onboard_rows.py` passes

## 3. Document the two rules of the webhook row

Kind: other. Reads: `src/devops_cli/github/onboard/service_rows.py`, `docs/repos/onboard.md`. Changes: `docs/repos/onboard.md`.

- [ ] 3.1 Rewrite the row 12 cell of the table in `docs/repos/onboard.md`: the state `person` with a step that names `service.webhook_url` when the setting holds its default value and no request to a hooks route; and a new secret to an existing hook only in a run that does row 13 with its deploy and passes its checks, else the difference with no write and a step that names the reason
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
