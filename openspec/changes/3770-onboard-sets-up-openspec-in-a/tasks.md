# Tasks

## 1. Add the OpenSpec row and its four states

Kind: behavior. Reads: `src/devops_cli/github/onboard/model.py`, `src/devops_cli/github/client.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/github/onboard/template_pr.py`, `tests/support/github_repository.py`, `tests/github/onboard/test_onboard_rows.py`, `tests/github/test_ci_job_time.py`. Changes: `src/devops_cli/github/onboard/model.py`, `src/devops_cli/github/onboard/openspec_row.py` (new), `src/devops_cli/github/client.py`, `tests/support/github_repository.py`, `tests/github/onboard/test_onboard_openspec.py` (new).
Adds: `openspec_row`, `folder_entries_at`

- [ ] 1.1 Write `test_openspec_row_reads_present`, `test_openspec_row_reads_missing`, `test_openspec_row_reads_invalid` and `test_openspec_row_reads_waiting_on_the_template_head` in `tests/github/onboard/test_onboard_openspec.py` first; they seed the OpenSpec config file and the specs placeholder in the commits of the fake repository and read row 16
  - Verification: `$ uv run devops ci test tests/github/onboard/test_onboard_openspec.py` fails on the base
- [ ] 1.2 Add `MISSING = "missing"` and `INVALID = "invalid"` to `RowState` in `src/devops_cli/github/onboard/model.py` and add both to `_FAILING_STATES` there. Add `openspec_row(session, ctx)` to `src/devops_cli/github/onboard/openspec_row.py`: it reads `CONST_OPENSPEC_CONFIG_PATH` at the default branch with `get_file_at`, parses the text with `yaml.safe_load`, checks the schema `spec-driven`, reads the entries under `CONST_OPENSPEC_SPECS_DIR` with `folder_entries_at`, and gives `present`, `missing` with the missing path in the reason, `invalid` with the failed condition in the reason, or `waiting` with the number of the open template pull request when the config file is on `ctx.template_head`. Add `folder_entries_at` to `src/devops_cli/github/client.py` next to `folder_names_at`. Change the contents route of `tests/support/github_repository.py` so a folder path answers the listing of its entries and a file path answers as it does now. The row sends no write
  - Verification: `$ uv run devops ci test tests/github/onboard/test_onboard_openspec.py` passes

## 2. Ship the project-neutral config template and add it to the template pull request

Kind: behavior. Reads: `src/devops_cli/github/onboard/template_pr.py`, `src/devops_cli/github/onboard/openspec_row.py`, `src/devops_cli/github/onboard/baseline.py`, `openspec/config.yaml`, `tests/github/onboard/test_onboard_rows.py`, `tests/infra/test_onboard.py`. Changes: `src/devops_cli/templates/openspec/config.yaml` (new), `src/devops_cli/github/onboard/openspec_row.py`, `src/devops_cli/github/onboard/template_pr.py`, `tests/github/onboard/test_onboard_openspec.py`.
Adds: `openspec_files`

- [ ] 2.1 Write `test_the_template_is_project_neutral` and `test_the_template_pull_request_adds_the_openspec_files` in `tests/github/onboard/test_onboard_openspec.py` first; the first names `src/devops_cli/templates/openspec/config.yaml`, and the second runs `--confirm` on a scratch repository and reads the one open pull request for `.github/labels.yml`, `openspec/config.yaml` and `openspec/specs/.gitkeep`
  - Verification: `$ uv run devops ci test tests/github/onboard/test_onboard_openspec.py` fails on the base
- [ ] 2.2 Add `src/devops_cli/templates/openspec/config.yaml` with a project-neutral context whose last line is marked for a person to fill in, with `rules` for proposal, specs, design and tasks, and with no text that names devops-cli. Add `openspec_files()` to `src/devops_cli/github/onboard/openspec_row.py`, which reads that package data file and gives the config file and the empty specs placeholder. In `src/devops_cli/github/onboard/template_pr.py`, merge those files into the file map that `template_row` compares and pushes before `_file_states`, so the one pull request of row 9 carries them, a file that the branch holds stays, and a second `--confirm` adds nothing
  - Verification: `$ uv run devops ci test tests/github/onboard/test_onboard_openspec.py` passes

## 3. Prove the merged tree with the real pinned validator

Kind: other. Reads: `tests/support/github_repository.py`, `tests/openspec/test_openspec_contract.py`, `src/devops_cli/openspec/tool.py`. Changes: `tests/github/onboard/test_onboard_openspec.py`.

- [ ] 3.1 Add `test_the_merged_tree_passes_openspec_validate_specs` to `tests/github/onboard/test_onboard_openspec.py`, marked `@pytest.mark.live("openspec")` as `tests/openspec/test_openspec_contract.py` does: build the scratch repository with the git fake, run `devops repos onboard --confirm`, call `merge_template_pull()`, write every file of the merged default branch under a temporary directory, run `validate --specs --strict` there through `isolated_openspec()`, and assert exit 0 and the two OpenSpec paths in the merged tree
  - Verification: `$ uv run devops ci test tests/github/onboard/test_onboard_openspec.py` passes

## 4. Run row 16 in the command and list its reads

Kind: behavior. Reads: `src/devops_cli/github/onboard/run.py`, `src/devops_cli/github/onboard/routes.py`, `src/devops_cli/github/onboard/openspec_row.py`, `tests/github/onboard/test_onboard_rows.py`, `tests/github/onboard/test_onboard_routes.py`, `tests/infra/test_onboard.py`. Changes: `src/devops_cli/github/onboard/run.py`, `src/devops_cli/github/onboard/routes.py`, `tests/github/onboard/test_onboard_rows.py`.

- [ ] 4.1 Update `test_a_second_confirmed_run_on_a_new_repository_writes_nothing` in `tests/github/onboard/test_onboard_rows.py` to expect row 16 `waiting` while the template pull request is open and `present` after its merge, and see it fail before row 16 runs
  - Verification: `$ uv run devops ci test tests/github/onboard/test_onboard_rows.py` fails on the base
- [ ] 4.2 Add `16: "OpenSpec"` to `ROW_NAMES` in `src/devops_cli/github/onboard/run.py` and call `run.put(16, lambda: openspec_row(session, ctx))` after `run.put(15, lambda: rag_row(writer, ctx, settings))`. Add the read of `CONST_OPENSPEC_CONFIG_PATH` and the read of the entries under `CONST_OPENSPEC_SPECS_DIR` for row 16 to `READS` in `src/devops_cli/github/onboard/routes.py`, so the dry run lists them. Update the expected rows of `tests/github/onboard/test_onboard_rows.py`, and seed `openspec/config.yaml` and `openspec/specs/.gitkeep` in the repository that the rows test calls onboarded
  - Verification: `$ uv run devops ci test tests/github/onboard/test_onboard_rows.py` passes

## 5. Describe row 16 in the onboard document

Kind: other. Reads: `docs/repos/onboard.md`, `src/devops_cli/github/onboard/run.py`. Changes: `docs/repos/onboard.md`.

- [ ] 5.1 Add row 16 OpenSpec to the row table of `docs/repos/onboard.md` with its states present, missing, invalid and waiting, and with the read of the config file and of the entries under the specs folder at the default branch. Say that the template pull request of row 9 carries the OpenSpec config file from `src/devops_cli/templates/openspec/config.yaml` and the specs placeholder, that it overwrites no file, that a second confirm writes nothing, and that a person fills the marked context line after the merge
  - Verification: `$ uv run devops ci docs` passes
- [ ] 5.2 Edit `docs/repos/onboard.md` to add row 16, its states, the shipped template and the specs placeholder
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 1: A new row `openspec` reads `present`, `missing` or `invalid`. It is `present` when `openspec/config.yaml` is on the default branch, names the schema `spec-driven`, and `openspec/specs/` exists.
- Group 2: With `--confirm`, the command opens one pull request that adds the missing files. It never overwrites a file that exists. A second `--confirm` writes nothing.
- Group 2: The `config.yaml` comes from a generic template that devops-cli ships (project-neutral `context` with a marked line for a person to fill in, and the `proposal`, `specs`, `design` and `tasks` rules that the planner needs). It does not copy the file of devops-cli.
- Group 3: After the pull request merges, `openspec validate --specs --strict` passes in the repository. A test shows this on a scratch repository built with the git fake.
- Group 2: The row for the `type/*` label rule of #3742 and this row use the same pull request, so one onboarding run opens one pull request.
- Group 5: `docs/roadmap/onboard.md` describes the row and the template.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
