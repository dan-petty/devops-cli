# Proposal

## Why

Row 12 of `devops repos onboard` plans a webhook to the example host for each repository when `service.webhook_url` holds its default value, and a confirmed run would create that hook (#7308). The same row also patches a new secret onto a live hook from a run that never pushes the secret to the cluster, so the Service refuses each delivery until `push-secrets` and `deploy-stack` run. The owner kept row 12 out of the run with `--only`, and the command must be safe with no such option.

## What Changes

- Row 12 reports `person` with a step that names `service.webhook_url` when the setting holds its default value, and sends no request to a repository hooks route.
- The default value moves to the constant `DEFAULT_SERVICE_WEBHOOK_URL` in `src/devops_cli/config/defaults.py`, so the setting and the guard read one value.
- Row 12 writes a new secret to an existing hook only in a run that does row 13 with its deploy and passes the clean-checkout checks of row 13; else it reports the difference and writes nothing.
- The run reads the deploy plan once, before row 12, and gives the same answer to rows 12 and 13.
- `tests/support/github_repository.py` names a set webhook URL, so the existing tests prove the guard instead of meeting it.
- `docs/repos/onboard.md` states both rules of row 12.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `repos-onboard`: A default webhook URL is a person step, The webhook secret write needs the Service row, The webhook row writes the hook and keeps its secret

## Impact

- Code: `src/devops_cli/config/defaults.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/github/onboard/service_rows.py`, `src/devops_cli/github/onboard/run.py`
- Documents: `docs/repos/onboard.md`
- Tests: `tests/support/github_repository.py`, `tests/commands/test_repos_onboard.py`, `tests/github/onboard/test_onboard_rows.py`

## Feasibility

- `probes` answered, word for word: The path `service.webhook_url` is no file of the staging commit. No commit in the history deleted or renamed it. The setting is a field of the settings model, so the probe found no removed path, and `read_file` confirmed the field below.
- `read_file` at lines 1858 to 1861 showed the field and its default: `src/devops_cli/config/settings.py:1858:webhook_url: Annotated[str, Variable()] = Field(` and `src/devops_cli/config/settings.py:1860:default="https://hooks.example.com/webhooks/github",`, which is the default that the issue names.
- `read_file` at lines 235 to 265 showed that row 12 reads the URL with no check that a person set it: `src/devops_cli/github/onboard/service_rows.py:248:url = settings.service.webhook_url`, which is the premise of the issue.
- The same read showed the write to a live hook and to the keyring: `src/devops_cli/github/onboard/service_rows.py:259:"hook-update", f"/repos/{ctx.repo}/hooks/{hook.id}", _hook_body(settings, secret)` and `src/devops_cli/github/onboard/service_rows.py:263:writer.run("webhook-secret", lambda: _store_secret(settings, ctx.repo, secret))`, so a run with row 13 out of `--only` still changes the hook.
- The map that the step names is the staged constant `src/devops_cli/github/onboard/service_rows.py:53:_WEBHOOK_SECRETS: Final[str] = "service.webhook_secrets"`.
- `read_file` at lines 110 to 112 and 243 to 244 showed the selected rows and the two calls: `src/devops_cli/github/onboard/run.py:110:def wanted(self, number: int) -> bool:`, `src/devops_cli/github/onboard/run.py:243:run.put(12, lambda: webhook_row(session, writer, ctx, settings))` and `src/devops_cli/github/onboard/run.py:244:run.put(13, lambda: service_row(writer, ctx, settings))`.
- `read_file` at lines 103 to 116 and 215 to 228 showed the two inputs of the guard: `src/devops_cli/github/onboard/model.py:114:deploy: bool = True` and `src/devops_cli/github/onboard/model.py:227:service_changed: bool = False`.
- `read_file` at lines 356 to 370 showed that a withheld write leaves row 13 `present` and that row 13 can refuse after row 12 wrote: `src/devops_cli/github/onboard/service_rows.py:357:if listed and not ctx.service_changed:`, `src/devops_cli/github/onboard/service_rows.py:367:reason = clean_main_reason(ctx.options.workdir)` and `src/devops_cli/github/onboard/service_rows.py:369:if reason is None and ctx.options.deploy:`.
- `read_file` at lines 506 to 528 showed the test that the new gate changes: `tests/github/onboard/test_onboard_rows.py:516:report = _run(onboard_github, confirm=True, deploy=False)`, `tests/github/onboard/test_onboard_rows.py:522:"PATCH /repos/example-org/app/hooks/9",`, `tests/github/onboard/test_onboard_rows.py:525:assert _row(report, 13).state is RowState.APPLIED` and `tests/github/onboard/test_onboard_rows.py:527:assert any("deploy-stack" in step.text for step in report.person_steps)`.
- `read_file` at line 388 showed that a missing hook stays outside the gate: `tests/github/onboard/test_onboard_rows.py:388:def test_a_new_hook_keeps_its_secret_in_the_keyring_only(onboard_github: OnboardHarness) -> None:` runs row 12 alone and expects the `POST`.
- `read_file` at lines 49 and 880 showed that the harness URL is the default today: `tests/support/github_repository.py:49:WEBHOOK_URL = "https://hooks.example.com/webhooks/github"` with `tests/support/github_repository.py:880:service={"repos": [], "webhook_url": WEBHOOK_URL, "github_app": APP_SETTINGS},`, so group 1 moves that constant to a set URL and the new tests pass the default through `tests/support/config.py:25:def config(isolate_devops_cli_config: Path) -> Callable[..., Path]:`.
- `references webhook_row` listed 2 files: `src/devops_cli/github/onboard/run.py:243:run.put(12, lambda: webhook_row(session, writer, ctx, settings))` and `src/devops_cli/github/onboard/service_rows.py:235:def webhook_row(`. Both sit in the `changes` of groups 1 and 2, and a search for `service_row(` found one call only, `src/devops_cli/github/onboard/run.py:244:run.put(13, lambda: service_row(writer, ctx, settings))`.
- `src/devops_cli/github/onboard/service_rows.py:235:def webhook_row(` needs a client of GitHub for the hooks, which the tests give as the fake transport of the harness at `tests/support/github_repository.py:775:class OnboardHarness:`.
- `src/devops_cli/github/onboard/service_rows.py:351:def service_row(writer: RouteWriter, ctx: RowContext, settings: Settings) -> Row:` needs a checkout of devops-cli and of the environment repository, which the harness makes at `tests/support/github_repository.py:883:checkout = tmp_path / "devops-cli"` and the autouse fixture at `tests/github/onboard/conftest.py:25:onboard_github: OnboardHarness, config: Callable[..., Path], tmp_path: Path` gives.
- `src/devops_cli/github/onboard/service_rows.py:290:def clean_main_reason(workdir: Path) -> str | None:` needs a checkout of the repository and a network for its `git fetch origin main`; the tests answer it with the fake process.
- `src/devops_cli/github/onboard/service_rows.py:305:def _deploy_tree(settings: Settings, workdir: Path) -> tuple[EnvironmentTree | None, str | None]:` needs a checkout of the environment repository, which the autouse fixture at `tests/github/onboard/conftest.py:37:config(infra={"repos": [{"repo": "example-org/infra", "path": str(repo)}]})` gives.
- `src/devops_cli/github/onboard/service_rows.py:324:def _run_devops(workdir: Path, *args: str) -> None:` needs a checkout, and it starts `devops k8s` only in a confirmed deploy; the tests answer it with the fake process.
- `src/devops_cli/github/onboard/run.py:213:def onboard_repository(` needs a client of GitHub and a checkout of the repository, which the harness gives at `tests/support/github_repository.py:883:checkout = tmp_path / "devops-cli"`.
- `docs/repos/onboard.md:58:| 12 | Webhook | Until #4417: the hook of` is the row cell that group 3 rewrites.
- No new program: the verifies `uv run devops ci test` and `uv run devops ci docs` run `pytest`, `ruff` and `mypy` from the runner image, which lists `pytest`, `ruff` and `mypy`, in a pod with `readOnlyRootFilesystem: true`, `runAsNonRoot: true` and `capabilities.drop: ALL`; the failure classes `test`, `lint` and `types` are those of that image, no test reaches the network, a cluster or a real scanner, and `tests/support/github_repository.py:775:class OnboardHarness:` doubles the GitHub client and the child processes.
- The first check against the real system is `uv run devops repos onboard --all --plan` on a workstation with no `service.webhook_url`, which shows row 12 as `person` with a step that names the setting and no hook change; then `uv run devops repos onboard example-org/app --plan`, and, from a clean checkout with row 13 in the run, `uv run devops repos onboard example-org/app --confirm --only 12,13`.

## Existing Tool Considered

The GitHub REST API for repository webhooks, which the command already uses, covers the hook reads and writes. No open, maintained tool covers a guard on a configuration default inside the onboard rows, and the alternatives check of 2026-11-26 in the issue body gives `none`. The change builds that guard itself at about 40k tokens to build, about 10k tokens to keep and fix, and about 4 hours elapsed.

## Dependencies

None.
