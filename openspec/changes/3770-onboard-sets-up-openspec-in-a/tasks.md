# Tasks

## 1. Add the OpenSpec row and its four states

Kind: behavior. Reads: `src/devops_cli/github/onboard/model.py`, `src/devops_cli/github/client.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/github/onboard/template_pr.py`, `tests/support/github_repository.py`, `tests/github/onboard/test_onboard_rows.py`. Changes: `src/devops_cli/github/onboard/model.py`, `src/devops_cli/github/onboard/openspec_row.py` (new), `src/devops_cli/github/client.py`, `tests/support/github_repository.py`, `tests/github/onboard/test_onboard_openspec.py` (new).
Adds: `openspec_row`, `folder_exists_at`

- [ ] 1.1 Write `test_openspec_row_reads_present`, `test_openspec_row_reads_missing`, `test_openspec_row_reads_invalid_for_another_schema`, `test_openspec_row_reads_invalid_for_text_that_does_not_parse`, `test_openspec_row_reads_invalid_with_no_specs_folder`, `test_openspec_row_reads_waiting_on_the_template_head`, `test_openspec_row_reads_waiting_when_the_template_head_adds_the_specs_folder` and `test_openspec_row_reads_missing_when_the_template_head_lacks_the_specs_folder` in `tests/github/onboard/test_onboard_openspec.py` first. Row 16 is not in the run until group 4, so each test calls `openspec_row(session, ctx)` directly with a `RowContext` whose `repo_payload`, `template_head` and `template_pull` it sets by hand, and seeds `openspec/config.yaml` and `openspec/specs/.gitkeep` in the commits of the fake repository of `onboard_github`
  - Verification: `$ uv run devops ci test tests/github/onboard/test_onboard_openspec.py` fails on the base
- [ ] 1.2 Add `MISSING = "missing"` and `INVALID = "invalid"` to `RowState` in `src/devops_cli/github/onboard/model.py` and add both to `_FAILING_STATES` there. Add `folder_exists_at(repo, path, ref) -> bool` to `src/devops_cli/github/client.py` next to `folder_names_at`: true when the contents answer of `path` at `ref` is a list, false on a 404 or a file. Add `openspec_row(session, ctx)` to `src/devops_cli/github/onboard/openspec_row.py`. It checks the present conditions at a ref: `CONST_OPENSPEC_CONFIG_PATH` read with `get_file_at` parses with `yaml.safe_load` and names the schema `spec-driven`, and `folder_exists_at` finds `CONST_OPENSPEC_SPECS_DIR`. It gives `present` when the default branch passes them, and `waiting` with the number of the open template pull request when the default branch fails them and `ctx.template_head` passes them. Otherwise the default branch alone decides: `missing` when it holds no config file, with the config path in the reason, and, when a template pull request is open, the condition that its head fails; `invalid` when it holds the config file, with the failed condition in the reason, and for a missing specs folder a reason that names the next step: `copier update` of the template, which Renovate brings, or a commit of `openspec/specs/.gitkeep`. Change the contents route of `tests/support/github_repository.py` so a folder path answers the listing of its entries and a file path answers as it does now. The row sends no write
  - Verification: `$ uv run devops ci test tests/github/onboard/test_onboard_openspec.py` passes

## 2. Prove that the template pull request carries the OpenSpec files of the template

Kind: other. Reads: `src/devops_cli/github/onboard/template_pr.py`, `src/devops_cli/github/onboard/baseline.py`, `tests/support/github_repository.py`, `tests/github/onboard/test_onboard_rows.py`. Changes: `tests/support/github_repository.py`, `tests/github/onboard/test_onboard_openspec.py`.

- [ ] 2.1 Add `openspec/config.yaml` and an empty `openspec/specs/.gitkeep` to the files of `render_template` in `tests/support/github_repository.py`, with a config text in the form of the OpenSpec config file of the repository template of dan-petty/infra: comment lines, then `schema: spec-driven`, a marked `Product:` context line and `rules` for proposal, specs, design and tasks. Write `test_the_template_pull_request_adds_the_openspec_files_of_the_template`, `test_a_config_file_that_exists_stays` and `test_a_second_confirm_adds_no_openspec_file` in `tests/github/onboard/test_onboard_openspec.py`. The first runs `--confirm` on a scratch repository of `onboard_github` and reads one open pull request whose `template-tree` request holds `.github/labels.yml`, `openspec/config.yaml` with the text of the render, and `openspec/specs/.gitkeep`. The second seeds `openspec/config.yaml` with other text on the default branch, and asserts that the changes of row 9 and the `template-tree` request name no `openspec/config.yaml` and that the file at the head of the pull request equals the seeded text. The third runs `--confirm` again and finds no new commit and no second pull request
  - Verification: `$ uv run devops ci test tests/github/onboard/test_onboard_openspec.py` passes

## 3. Prove the merged tree with the real pinned validator

Kind: other. Reads: `tests/support/github_repository.py`, `tests/support/fakes/process.py`, `tests/openspec/test_openspec_contract.py`, `src/devops_cli/openspec/tool.py`, `src/devops_cli/core/process.py`. Changes: `tests/github/onboard/test_onboard_openspec.py`.

- [ ] 3.1 Add `test_the_merged_tree_passes_openspec_validate_specs` to `tests/github/onboard/test_onboard_openspec.py`, marked `@pytest.mark.live("openspec")` as `tests/openspec/test_openspec_contract.py` does: build the scratch repository with `onboard_github`, run `devops repos onboard --confirm`, call `merge_template_pull()`, and write every file of the merged default branch under a temporary directory. The fixture installs the process fake, which answers an unknown call with exit 0 and fakes `shutil.which`, so set the real runner with `set_process_runner(DefaultProcessRunner())` around the whole `with isolated_openspec()` block (its settings runs start on entry), put the fake runner back after it, and assert that `harness.processes.calls` holds no `openspec` call. Run `validate --specs --strict` through `isolated_openspec()` and assert exit 0 and the two OpenSpec paths in the merged tree. The validator 2.2.0 also passes a tree with another schema, so this test proves the merged tree parses, and the row tests of group 1 carry the schema check
  - Verification: `$ uv run devops ci test tests/github/onboard/test_onboard_openspec.py` passes

## 4. Run row 16 in the command, list its reads and count its states as drift

Kind: behavior. Reads: `src/devops_cli/github/onboard/run.py`, `src/devops_cli/github/onboard/routes.py`, `src/devops_cli/github/onboard/drift.py`, `src/devops_cli/github/onboard/openspec_row.py`, `tests/github/onboard/test_onboard_rows.py`, `tests/github/onboard/test_onboard_routes.py`. Changes: `src/devops_cli/github/onboard/run.py`, `src/devops_cli/github/onboard/routes.py`, `src/devops_cli/github/onboard/drift.py`, `tests/github/onboard/test_onboard_rows.py`.

- [ ] 4.1 Update `test_a_second_confirmed_run_on_a_new_repository_writes_nothing` and `test_an_onboarded_repository_plans_no_change` in `tests/github/onboard/test_onboard_rows.py`: expect row 16 `waiting` in the first confirm run, where row 11 turns on auto-merge and does not merge; assert `_row(second, 16).state` and `_row(report, 16).state` are `present` after the merge and in the onboarded repository; and add a test that a plan run with row 16 `invalid` reports the repository as drift. See them fail before row 16 runs
  - Verification: `$ uv run devops ci test tests/github/onboard/test_onboard_rows.py` fails on the base
- [ ] 4.2 Add `16: "OpenSpec"` to `ROW_NAMES` in `src/devops_cli/github/onboard/run.py` and call `run.put(16, lambda: openspec_row(session, ctx))` after `run.put(15, lambda: rag_row(writer, ctx, settings))`. Add the reads of row 16 to `READS` in `src/devops_cli/github/onboard/routes.py`: the config file and the specs folder at the default branch and at the head of the open template pull request, so the dry run lists them. Add `RowState.MISSING` and `RowState.INVALID` to `_DRIFT_STATES` in `src/devops_cli/github/onboard/drift.py`, because both make the command exit 1
  - Verification: `$ uv run devops ci test tests/github/onboard/test_onboard_rows.py` passes

## 5. Accept row 16 in `--only`

Kind: behavior. Reads: `src/devops_cli/commands/repos.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/github/onboard/run.py`, `tests/commands/test_repos_onboard.py`. Changes: `src/devops_cli/commands/repos.py`, `src/devops_cli/lang/en/messages.py`, `tests/commands/test_repos_onboard.py`.

- [ ] 5.1 Add `test_only_takes_the_openspec_row` to `tests/commands/test_repos_onboard.py`: the command `repos onboard <repo> --plan --only 16` is not refused, and `--only 17` is refused with a message that names 16 as the last row
  - Verification: `$ uv run devops ci test tests/commands/test_repos_onboard.py` fails on the base
- [ ] 5.2 Make the row numbers of `_onboard_rows` in `src/devops_cli/commands/repos.py` the keys of `ROW_NAMES` of `src/devops_cli/github/onboard/run.py`, imported inside the function as the command imports the onboard modules, and make `onboard_only_invalid` in `src/devops_cli/lang/en/messages.py` take the last row number as a field, so a new row needs no second edit
  - Verification: `$ uv run devops ci test tests/commands/test_repos_onboard.py` passes
- [ ] 5.3 Regenerate the documentation of the changed message with `uv run devops docs generate`
  - Verification: `$ uv run devops docs generate --check` passes

## 6. Describe row 16 in the onboard document

Kind: other. Reads: `docs/repos/onboard.md`, `src/devops_cli/github/onboard/run.py`, `src/devops_cli/github/onboard/drift.py`. Changes: `docs/repos/onboard.md`.

- [ ] 6.1 Add row 16 OpenSpec to the row table of `docs/repos/onboard.md` with its states present, missing, invalid and waiting, and with the reads of the config file and of the specs folder. Add `missing` and `invalid` to the list of states of the document, to the drift states, and to the section of the nightly Job with the reason that row 16 is or is not in its `--only` list. Say that the template pull request of row 9 adds `openspec/config.yaml` and `openspec/specs/.gitkeep` from the repository template of dan-petty/infra, that it overwrites no file, that a second confirm writes nothing, that `--only 16` reads the default branch alone because row 9 does not run, and that a person fills the marked `Product:` context line after the merge
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 1: A new row `openspec` reads `present`, `missing` or `invalid`. It is `present` when `openspec/config.yaml` is on the default branch, names the schema `spec-driven`, and `openspec/specs/` exists.
- Group 2: With `--confirm`, the command opens one pull request that adds the missing files. It never overwrites a file that exists. A second `--confirm` writes nothing.
- Group 2: The `config.yaml` comes from the template of dan-petty/infra, not from a template that devops-cli ships (project-neutral `context` with a marked line for a person to fill in, and the `proposal`, `specs`, `design` and `tasks` rules that the planner needs). It does not copy the file of devops-cli.
- Group 3: After the pull request merges, `openspec validate --specs --strict` passes in the repository. A test shows this on a scratch repository built with the git fake.
- Group 2: The row for the `type/*` label rule of #3742 and this row use the same pull request, so one onboarding run opens one pull request.
- Group 6: `docs/repos/onboard.md` describes the row and the template.

## Workflow follow-up

- Follow-up dan-petty/infra#201: the repository template adds `openspec/specs/.gitkeep`. Until a release of dan-petty/infra holds it, a repository that onboards reads row 16 `invalid` after the merge of its template pull request.
- Pending a person: after the release of dan-petty/infra#201, run `uv run devops repos onboard dan-petty/devtools --plan --only 16`, which must print row 16 `invalid` with the `copier update` step in its reason until the copier update of devtools merges, and `present` after it.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
