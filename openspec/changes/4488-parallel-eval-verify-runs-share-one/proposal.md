# Proposal

## Why

Two `devops roadmap eval verify` runs that start in the same second share one report file, and each atomic write replaces the cases of the other run, so the parallel workflow that the workflow document recommends loses cases with no warning. #4488 asks each run without `--resume` to create its own report file and to write every later report of the run to it.

## What Changes

- Add `create_store_file` to `src/devops_cli/core/repo.py`, next to `resolve_store_path`: it creates the store folder, creates the file exclusively with `tempfile.mkstemp`, and returns the path of a new file whose name starts with the moment.
- Use the helper in `src/devops_cli/commands/roadmap_eval_verify.py` through a `_report_target` function, so a run without `--resume` gets its own report file and every later write of the run goes to it.
- Keep `--resume <report>` writing only the named report and creating no new report file.
- Add the offline tests in `tests/core/test_core_repo.py` and the new module `tests/commands/test_roadmap_eval_verify_store.py`: two files in one second, a missing store folder, and a resumed run.
- Update `docs/ROADMAP_WORKFLOW.md` to state that each run without `--resume` creates its own report file.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage-eval`: The verify command creates its own report file, A resumed run keeps the report it names, A store file gets a unique name

## Impact

- Code: `src/devops_cli/core/repo.py`, `src/devops_cli/commands/roadmap_eval_verify.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`
- Tests: `tests/core/test_core_repo.py`, `tests/commands/test_roadmap_eval_verify_store.py`

## Feasibility

- `read_file` of `src/devops_cli/commands/roadmap_eval_verify.py` showed `src/devops_cli/commands/roadmap_eval_verify.py:118:target = resume or resolve_store_path(`, so the name comes from `datetime.now(UTC)` with `%Y%m%dT%H%M%SZ` and nothing creates the file exclusively.
- The probe confirms the cited command file word for word: "The path `src/devops_cli/commands/roadmap_eval_verify.py` is a file of the staging commit."
- The probe confirms the cited document word for word: "The path `docs/ROADMAP_WORKFLOW.md` is a file of the staging commit."
- `read_file` showed `docs/ROADMAP_WORKFLOW.md:375:To split the set between processes`; the issue cites line 374, and the staged commit holds that sentence at line 375.
- The probe shows the short path of another eval command is a candidate at another location, word for word: "The path `roadmap_eval_stage.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/commands/roadmap_eval_stage.py`."
- The probe line "The path `os.replace` is no file of the staging commit. No commit in the history deleted or renamed it." shows that `os.replace` is no repository path; the atomic write is `src/devops_cli/output/file_writer.py:def write_text_file`.
- `read_file` showed the existing exclusive create: `src/devops_cli/roadmap/implement/implement_eval_run.py:455:directory.mkdir(parents=True, exist_ok=True)` and then `src/devops_cli/roadmap/implement/implement_eval_run.py:457:tempfile.mkstemp(prefix=f"implement-{stamp}-"`.
- `read_file` showed `src/devops_cli/core/repo.py:def resolve_store_path`, which resolves a store name under `data.dir`; the new helper goes next to it.
- `read_file` showed the existing test of the command module: `tests/roadmap/stage/test_roadmap_stage_verify_eval.py:14:from devops_cli.commands.roadmap_eval_verify import _review_model`; `tests/core/test_core_repo.py` is the existing test of the module that gets the helper.
- `find_issues` with the words `roadmap eval verify report` listed #4488 and nine other open items; none names the report path that this plan changes, so the plan has no dependency.
- `resolve_store_path` reads the settings and the data directory, and needs no checkout, client or network.
- `load_settings` reads the configuration files, and needs no checkout, client or network.
- `tempfile.mkstemp` creates the file in the store folder, and needs no checkout, client or network.
- `Path.mkdir` creates the store folder, and needs no checkout, client or network.
- The verify commands are the existing `uv run devops ci test`; `uv`, `python`, `pytest` and `devops` are in the runner image, a failing test is the failure class `test`, and no new class or program is introduced.
- The pod setting that applies is `readOnlyRootFilesystem: true`, so the new tests set `DEVOPS_CLI_DATA_DIR` to a `tmp_path` folder and write nothing else; the command verify runs in the checkout of the repository.
- The first checks are `uv run devops ci test tests/core/test_core_repo.py` and `uv run devops ci test tests/commands/test_roadmap_eval_verify_store.py`, and the document group runs `uv run devops ci test tests/invariants/test_roadmap_workflow_doc.py`.

## Existing Tool Considered

The Python standard library `tempfile.mkstemp` covers exclusive file creation, and the project already uses it in `src/devops_cli/roadmap/implement/implement_eval_run.py` (`write_report`) and in `src/devops_cli/docker/cosign.py`. The change builds no unique-name generator of its own.

## Dependencies

None.
