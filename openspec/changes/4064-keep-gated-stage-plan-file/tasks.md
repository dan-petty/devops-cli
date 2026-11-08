# Tasks

## 1. Keep the plan in a file with a key of its input

Kind: behavior

Reads: `src/devops_cli/roadmap/run.py`, `src/devops_cli/roadmap/body_hash.py`, `src/devops_cli/roadmap/stage/stage_request.py`, `src/devops_cli/roadmap/stage/stage_toolbox.py`, `src/devops_cli/roadmap/stage/stage_split.py`. Changes: `src/devops_cli/roadmap/stage/stage_plan_record.py` (new), `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_plan_record.py` (new).

- [x] 1.1 Write `tests/roadmap/stage/test_roadmap_stage_plan_record.py` for the record: the key follows its seven inputs and not the staged commit, the prompt version follows the prompt texts and the toolset, the path is `roadmap/stage/<owner>/<repo>/<number>.json` under the data directory, a written file reads back and leaves no temporary file, and an unreadable file raises an error that names the file
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [ ] 1.2 Add `src/devops_cli/roadmap/stage/stage_plan_record.py` with `StagePlanRecord`, `plan_key`, `prompt_version`, `plan_record_path`, `read_plan_record`, `write_plan_record` and `delete_plan_record`, built on `write_json_file(..., atomic=True)`, `body_hashes` and `load_task_prompt`. Add the message of the unreadable file to `src/devops_cli/lang/en/messages.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_plan_record.py -k "key or unreadable or record"`

## 2. Plan from the kept file and count each use

Kind: behavior

Reads: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/telemetry/instruments.py`. Changes: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/telemetry/instruments.py`, `tests/roadmap/stage/test_roadmap_stage_plan_record.py`.

- [x] 2.1 Add to the test file the tests of the planner: a failed review and a rerun, `--plan` then `--confirm`, a moved commit, a changed body, a changed prompt, the golden set that keeps no file, and the counter
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [ ] 2.2 Give `_Planner` the file directory, the model name and the toolset name. In `plan`, read the file by the key, delete a file of another key, take a hit as the first reply of `_gated`, and write the file after `_gated` returns a change. Add the instrument `ROADMAP_STAGE_PLAN_RECORD_TOTAL` and emit `hit`, `miss` and `written`. `plan_stage` passes the directory, the model name and the toolset, and `plan_item` passes none
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_plan_record.py`

## 3. Delete the file when the item is staged

Kind: behavior

Reads: `src/devops_cli/roadmap/stage/stage.py`. Changes: `src/devops_cli/roadmap/stage/stage.py`, `tests/roadmap/stage/test_roadmap_stage_plan_record.py`.

- [x] 3.1 Add to the test file a staged item that deletes its file and a failed write that keeps it
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [ ] 3.2 In `StageWriter._stage`, delete the plan file after `_stage_one` succeeds
  - Verification: `$ uv run devops ci test tests/roadmap/stage`

## 4. State the new contract of --plan in the help and the documents

Kind: behavior

Reads: `src/devops_cli/lang/en/help.py`, `docs/roadmap/stage.md`, `docs/TELEMETRY.md`. Changes: `src/devops_cli/lang/en/help.py`, `docs/roadmap/stage.md`, `docs/TELEMETRY.md`, `tests/roadmap/test_roadmap_command_help.py`.

- [x] 4.1 Add `test_the_help_and_the_page_of_stage_plan_say_one_local_file_and_no_github_write` to `tests/roadmap/test_roadmap_command_help.py`
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [ ] 4.2 Change `stage_plan` in `src/devops_cli/lang/en/help.py` and the `--plan` row of `docs/roadmap/stage.md` to say that `--plan` writes one local file and no GitHub write, add a paragraph to the page that tells the key, the file and the delete, and add the row of `devops_cli_roadmap_stage_plan_record_total` to `docs/TELEMETRY.md`. Run `uv run devops docs generate --sync-readme`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_command_help.py`

## Workflow follow-up

- Pending a person: read the counter `devops_cli_roadmap_stage_plan_record_total` 14 days after the merge. If it shows no hit, decide whether to remove the file (#4064).
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
