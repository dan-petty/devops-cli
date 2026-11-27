# Design

## Decisions

- **Compare the resolved `service.webhook_url` with the constant `DEFAULT_SERVICE_WEBHOOK_URL`, which holds the field default**: It reads the same resolved setting that row 12 reads now, so a value from the file, the environment or the keyring counts alike, and the config loader does not change.
- **Read the deploy plan once before row 12 and give the same plan to rows 12 and 13**: `src/devops_cli/github/onboard/service_rows.py:367:reason = clean_main_reason(ctx.options.workdir)` runs after row 12 wrote, and `src/devops_cli/github/onboard/service_rows.py:369:if reason is None and ctx.options.deploy:` reads the tree after it; one read before row 12 keeps both rows on one answer and still refuses row 13 as before.
- **Report the withheld secret as `pending` with one person step and write nothing**: `src/devops_cli/github/onboard/model.py:31:{RowState.PENDING, RowState.FAILED, RowState.NOT_READABLE}` makes `pending` a failing state, so the run exits 1 and the person sees the drift; the step names `service.webhook_secrets` and the reason that keeps the write away.
- **Report the state `person` with a step that names `service.webhook_url` when the URL is the default, before the row reads the hooks**: The row then sends no request to a hooks route, and the step names the setting that the cluster values would give.
- **Leave the `POST` of a missing hook outside the deploy gate**: A missing hook carries no working delivery to break, and `tests/github/onboard/test_onboard_rows.py:388:def test_a_new_hook_keeps_its_secret_in_the_keyring_only(onboard_github: OnboardHarness) -> None:` runs row 12 alone and expects the `POST`.
- **Give the test harness the set URL `https://webhooks.example.com/github` and keep the default value in `DEFAULT_SERVICE_WEBHOOK_URL`**: `tests/support/github_repository.py:880:service={"repos": [], "webhook_url": WEBHOOK_URL, "github_app": APP_SETTINGS},` would otherwise make each existing test meet the new person step.
- **Change the drift test to row 12 `pending`, row 13 `present`, no hook PATCH and no deploy-stack step**: The withheld write sets no `ctx.service_changed`, and `src/devops_cli/github/onboard/service_rows.py:357:if listed and not ctx.service_changed:` makes row 13 `present` with no deploy step, while `tests/github/onboard/test_onboard_rows.py:516:report = _run(onboard_github, confirm=True, deploy=False)` runs no deploy.
- **Write the default value into the test configuration rather than deleting the key from the file**: Row 12 compares the resolved value with the constant, so a written default and an absent key give the same input, and the test keeps the `config` fixture that `tests/support/config.py:25:def config(isolate_devops_cli_config: Path) -> Callable[..., Path]:` gives.
- **Test the guard with one repository and `--confirm`**: `src/devops_cli/commands/repos.py:1053:raise typer.BadParameter(MESSAGES.repos.onboard_all_confirm)` refuses `--all` with `--confirm`, so the guard is tested with one repository.

## Rejected alternatives

- **Check the pydantic-settings `model_fields_set` to learn whether a person set the URL**: `tests/support/github_repository.py:880:service={"repos": [], "webhook_url": WEBHOOK_URL, "github_app": APP_SETTINGS},` shows a config that names the key, and a merged config that repeats the default makes the field look set.
- **Read the raw config file for the `service.webhook_url` key**: `src/devops_cli/config/env.py:def option_env_vars` derives the variable `DEVOPS_CLI_SERVICE_WEBHOOK_URL` of the setting, so the file alone misses a value that the environment gives.
- **Read the command line again in row 12**: `src/devops_cli/github/onboard/run.py:110:def wanted(self, number: int) -> bool:` holds the selected rows of the run, so a second read of the parser hides an input that the run already has.
- **Gate the secret write on `--only` and `--no-deploy` alone**: `src/devops_cli/github/onboard/service_rows.py:367:reason = clean_main_reason(ctx.options.workdir)` shows that row 13 can refuse after row 12 wrote, and the cluster then never gets the secret.
- **Call `clean_main_reason` and `_deploy_tree` a second time inside row 12**: `src/devops_cli/github/onboard/service_rows.py:290:def clean_main_reason(workdir: Path) -> str | None:` runs `git fetch origin main`, so a second call is 2 fetches and 2 reads of the environment tree for 1 answer, and the two answers can differ.
- **Report the state `person` when the URL is set and the run cannot deploy**: `src/devops_cli/github/onboard/service_rows.py:169:def webhook_step(settings: Settings) -> PersonStep:` is the step for a hook that a person adds by hand, which does not apply when the hook exists and only its secret differs.

## Unchanged references

- `docs/CONFIGURATION.md` (generated document): The default value and the description of the setting stay the same, so the generated table keeps its row.
- `docs/ENV_VARS.md` (generated document): The variable and the description of the setting stay the same.
- `tests/security/test_config_declarations.py` (quoted target): It names the variable `DEVOPS_CLI_SERVICE_WEBHOOK_URL`, whose name stays.

## Security

A webhook HMAC secret crosses a trust boundary: row 12 writes it to a live GitHub hook and into the OS keyring map `service.webhook_secrets`, and row 13 pushes it to the cluster. A person must confirm that a run which writes a secret to an existing hook also deploys that secret in the same run, because a hook whose secret the cluster lacks refuses every delivery. `tests/github/onboard/test_onboard_rows.py` fails if a run without the deploy patches a secret or stores one, and no secret reaches the output, a log or an argument.
