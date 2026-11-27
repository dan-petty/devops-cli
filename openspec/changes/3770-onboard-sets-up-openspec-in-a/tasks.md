# Tasks

## 1. Add the OpenSpec row and its four states

Kind: behavior. Reads: `src/devops_cli/github/onboard/model.py`, `src/devops_cli/github/client.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/github/onboard/template_pr.py`, `tests/support/github_repository.py`, `tests/github/onboard/test_onboard_rows.py`. Changes: `src/devops_cli/github/onboard/model.py`, `src/devops_cli/github/onboard/openspec_row.py` (new), `src/devops_cli/github/client.py`, `tests/support/github_repository.py`, `tests/github/onboard/test_onboard_openspec.py` (new).
Adds: `openspec_row`, `folder_exists_at`

- [ ] 1.1 Write `test_openspec_row_reads_present`, `test_openspec_row_reads_missing`, `test_openspec_row_reads_invalid_for_another_schema`, `test_openspec_row_reads_invalid_for_text_that_does_not_parse`, `test_openspec_row_reads_invalid_with_no_specs_folder` and `test_openspec_row_reads_waiting_on_the_template_head` in `tests/github/onboard/test_onboard_openspec.py` first; they seed `openspec/config.yaml` and `openspec/specs/.gitkeep` in the commits of the fake repository and read row 16
  - Verification: `$ uv run devops ci test tests/github/onboard/test_onboard_openspec.py` fails on the base
- [ ] 1.2 Add `MISSING = "missing"` and `INVALID = "invalid"` to `RowState` in `src/devops_cli/github/onboard/model.py` and add both to `_FAILING_STATES` there. Add `folder_exists_at(repo, path, ref) -> bool` to `src/devops_cli/github/client.py` next to `folder_names_at`: true when the contents answer of `path` at `ref` is a list, false on a 404 or a file. Add `openspec_row(session, ctx)` to `src/devops_cli/github/onboard/openspec_row.py`: it reads `CONST_OPENSPEC_CONFIG_PATH` at the default branch with `get_file_at`, parses the text with `yaml.safe_load`, checks the schema `spec-driven`, checks `CONST_OPENSPEC_SPECS_DIR` with `folder_exists_at`, and gives `present`; `missing` with the config path in the reason; `invalid` with the failed condition in the reason; or `waiting` with the number of the open template pull request when the default branch holds no config file and `ctx.template_head` holds it. Change the contents route of `tests/support/github_repository.py` so a folder path answers the listing of its entries and a file path answers as it does now. The row sends no write
  - Verification: `$ uv run devops ci test tests/github/onboard/test_onboard_openspec.py` passes

## 2. Prove that the template pull request carries the OpenSpec files of the template

Kind: other. Reads: `src/devops_cli/github/onboard/template_pr.py`, `src/devops_cli/github/onboard/baseline.py`, `tests/support/github_repository.py`, `tests/github/onboard/test_onboard_rows.py`. Changes: `tests/support/github_repository.py`, `tests/github/onboard/test_onboard_openspec.py`.

- [ ] 2.1 Add `openspec/config.yaml` and an empty `openspec/specs/.gitkeep` to the files of `render_template` in `tests/support/github_repository.py`, with a config text in the form of the OpenSpec config file of the repository template of dan-petty/infra: `schema: spec-driven`, a marked `Product:` context line and `rules` for proposal, specs, design and tasks. Write `test_the_template_pull_request_adds_the_openspec_files_of_the_template`, `test_a_config_file_that_exists_stays` and `test_a_second_confirm_adds_no_openspec_file` in `tests/github/onboard/test_onboard_openspec.py`: the first runs `--confirm` on a scratch repository and reads one open pull request that holds `.github/labels.yml`, `openspec/config.yaml` with the text of the render, and `openspec/specs/.gitkeep`; the second seeds `openspec/config.yaml` with other text on the default branch and finds no `openspec/config.yaml` in the commit of the pull request; the third runs `--confirm` again and finds no new commit and no second pull request
  - Verification: `$ uv run devops ci test tests/github/onboard/test_onboard_openspec.py` passes

## 3. Prove the merged tree with the real pinned validator

Kind: other. Reads: `tests/support/github_repository.py`, `tests/openspec/test_openspec_contract.py`, `src/devops_cli/openspec/tool.py`. Changes: `tests/github/onboard/test_onboard_openspec.py`.

- [ ] 3.1 Add `test_the_merged_tree_passes_openspec_validate_specs` to `tests/github/onboard/test_onboard_openspec.py`, marked `@pytest.mark.live("openspec")` as `tests/openspec/test_openspec_contract.py` does: build the scratch repository with the git fake, run `devops repos onboard --confirm`, call `merge_template_pull()`, write every file of the merged default branch under a temporary directory, run `validate --specs --strict` there through `isolated_openspec()`, and assert exit 0 and the two OpenSpec paths in the merged tree
  - Verification: `$ uv run devops ci test tests/github/onboard/test_onboard_openspec.py` passes

## 4. Run row 16 in the command and list its reads

Kind: behavior. Reads: `src/devops_cli/github/onboard/run.py`, `src/devops_cli/github/onboard/routes.py`, `src/devops_cli/github/onboard/openspec_row.py`, `tests/github/onboard/test_onboard_rows.py`, `tests/github/onboard/test_onboard_routes.py`. Changes: `src/devops_cli/github/onboard/run.py`, `src/devops_cli/github/onboard/routes.py`, `tests/github/onboard/test_onboard_rows.py`.

- [ ] 4.1 Update `test_a_second_confirmed_run_on_a_new_repository_writes_nothing` and `test_an_onboarded_repository_plans_no_change` in `tests/github/onboard/test_onboard_rows.py` to expect row 16: `waiting` while the template pull request is open, `present` after its merge, and `present` in the onboarded repository; see them fail before row 16 runs
  - Verification: `$ uv run devops ci test tests/github/onboard/test_onboard_rows.py` fails on the base
- [ ] 4.2 Add `16: "OpenSpec"` to `ROW_NAMES` in `src/devops_cli/github/onboard/run.py` and call `run.put(16, lambda: openspec_row(session, ctx))` after `run.put(15, lambda: rag_row(writer, ctx, settings))`. Add the read of `CONST_OPENSPEC_CONFIG_PATH` and the read of `CONST_OPENSPEC_SPECS_DIR` for row 16 to `READS` in `src/devops_cli/github/onboard/routes.py`, so the dry run lists them
  - Verification: `$ uv run devops ci test tests/github/onboard/test_onboard_rows.py` passes

## 5. Describe row 16 in the onboard document

Kind: other. Reads: `docs/repos/onboard.md`, `src/devops_cli/github/onboard/run.py`. Changes: `docs/repos/onboard.md`.

- [ ] 5.1 Add row 16 OpenSpec to the row table of `docs/repos/onboard.md` with its states present, missing, invalid and waiting, and with the reads of the config file and of the specs folder at the default branch. Say that the template pull request of row 9 adds `openspec/config.yaml` and `openspec/specs/.gitkeep` from the repository template of dan-petty/infra, that it overwrites no file, that a second confirm writes nothing, and that a person fills the marked `Product:` context line after the merge
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 1: A new row `openspec` reads `present`, `missing` or `invalid`. It is `present` when `openspec/config.yaml` is on the default branch, names the schema `spec-driven`, and `openspec/specs/` exists.
- Group 2: With `--confirm`, the command opens one pull request that adds the missing files. It never overwrites a file that exists. A second `--confirm` writes nothing.
- Group 2: The `config.yaml` comes from the template of dan-petty/infra, not from a template that devops-cli ships (project-neutral `context` with a marked line for a person to fill in, and the `proposal`, `specs`, `design` and `tasks` rules that the planner needs). It does not copy the file of devops-cli.
- Group 3: After the pull request merges, `openspec validate --specs --strict` passes in the repository. A test shows this on a scratch repository built with the git fake.
- Group 2: The row for the `type/*` label rule of #3742 and this row use the same pull request, so one onboarding run opens one pull request.
- Group 5: `docs/repos/onboard.md` describes the row and the template.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
