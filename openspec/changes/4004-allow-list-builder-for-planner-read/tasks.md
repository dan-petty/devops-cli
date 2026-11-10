# Tasks

## 1. Build the allow-list and the refusal from the exposure table and the two path records

Reads: `src/devops_cli/config/constants.py`, `src/devops_cli/ai/mcp/generator.py`, `src/devops_cli/ai/mcp/path_confinement.py`, `tests/ai/mcp/test_path_confinement.py`, `src/devops_cli/commands/scan.py`. Changes: `src/devops_cli/roadmap/stage/stage_run_allowlist.py` (new), `tests/roadmap/stage/test_stage_run_allowlist.py` (new).

- [ ] 1.1 `tests/roadmap/stage/test_stage_run_allowlist.py::test_a_text_path_option_leaves_its_command_out` fails first, because the module and its builder do not exist yet
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_stage_run_allowlist.py` fails on the base
- [ ] 1.2 Write `tests/roadmap/stage/test_stage_run_allowlist.py` first. Give it one case for each scenario: the entry for `gh labels list` with `repo`; no entry for `valkey flush` and the reason `not read-only`; no entry for `tf plan`, for `ai read` and for `scan sast` and the reason `path option`; `telemetry profile` with one option; the `help` option permitted for `valkey flush`; `config unset` refused with `unknown command`; `ai benchmark` with `output` refused with `option not permitted`; and `repo` accepted for `gh labels list`. Add a case that a command whose only path parameter is a text option stays out: build a small Typer app with a `config: str` option, give its tool name an entry in the confinement table with monkeypatch, and assert the row leaves. Add a census test that walks every row of the exposure table, decides each one, and fails when the count is not 144. Then add `src/devops_cli/roadmap/stage/stage_run_allowlist.py`: the four reason constants; the frozen refusal with its path, reason and option fields; `build_allowlist()`, which walks `CONST_MCP_EXPOSURE_TABLE`, skips a row that is not read-only, resolves the Click command, applies the ignored and JSON parameter filters and the `allowed` set of `_PATH_PARAM_RESTRICTIONS`, computes the tool name as the joined path with `-` replaced by `_`, leaves the row out when a permitted parameter is typed as a path or is named by `PATH_CONFINEMENTS` for that tool name, and otherwise maps the path to the permitted parameter names; and `check_command(path, options)`, which permits the `help` option for a path the Click tree resolves and otherwise returns the refusal. Leave out a row whose command the Click tree no longer resolves. Keep `vault get` in the table, because its path parameter is no file path and its `show` option is withheld
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_stage_run_allowlist.py` passes

## 2. List the new module in the package layout

Reads: `docs/roadmap/package-layout.md`, `src/devops_cli/roadmap/stage/stage_run_allowlist.py`. Changes: `docs/roadmap/package-layout.md`.

- [ ] 2.1 Edit `docs/roadmap/package-layout.md` to add `stage_run_allowlist` to the module list of the `stage/` row, between `stage_request` and `stage_specs`, so the layout names the module that holds the command policy of the planner's run tool
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
