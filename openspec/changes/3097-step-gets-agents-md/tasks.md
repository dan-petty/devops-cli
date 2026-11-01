# Tasks

## 1. The routes table

Reads: `src/devops_cli/roadmap/step_files.py`, `src/devops_cli/roadmap/implement_step.py`. Changes: `src/devops_cli/roadmap/step_rules.py` (new), `src/devops_cli/roadmap/step_files.py`, `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/implement_run.py`, `tests/roadmap/test_roadmap_step_rules.py` (new).

- [x] 1.1 Write failing tests in `tests/roadmap/test_roadmap_step_rules.py`: each route names a row of the "Where to look" table of `AGENTS.md` that links its document, the document exists, each section exists, and the selected text fits `CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS`; `rules_sections` gives `AGENTS.md` verbatim, gives `docs/TESTING.md` for a group that names a test file (also one that does not exist yet, and a `::test` suffix), gives nothing of it for a group that names only a manifest, gives only `AGENTS.md` for a group with no path, and gives nothing for a checkout with no `AGENTS.md`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_step_rules.py` fails on the base
- [x] 1.2 Move `section_text` from `implement_step.py` to `step_files.py`, and add `ROUTES`, `Route` and `rules_sections` in `src/devops_cli/roadmap/step_rules.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_step_rules.py tests/roadmap/test_roadmap_implement_step.py` passes

## 2. The message and the measure

Reads: `src/devops_cli/roadmap/step_rules.py`, `src/devops_cli/roadmap/stage_change.py`. Changes: `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/stage_change.py`, `tests/roadmap/test_roadmap_implement_step_rules.py` (new), `tests/roadmap/test_roadmap_stage_measure.py`.

- [x] 2.1 Write failing tests: the first request of a stub model holds `AGENTS.md` verbatim under its heading and the sections of `docs/TESTING.md` for a group with a test file; a manifest-only group has no `docs/TESTING.md`; the count against the window includes them; a fix step holds `AGENTS.md` and no routed section; the stage measure of a group equals the old measure plus the tokens of `rules_sections`, and the measure and the step message hold the same sections
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step_rules.py tests/roadmap/test_roadmap_stage_measure.py` fails on the base
- [x] 2.2 Add the sections to `build_step_inputs` and to `measure_groups`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step_rules.py tests/roadmap/test_roadmap_stage_measure.py tests/roadmap/test_roadmap_implement_step.py tests/roadmap/test_roadmap_stage_plan.py tests/roadmap/test_roadmap_stage_apply.py`

## 3. The prompt keeps the runner facts

Reads: `src/devops_cli/ai/tasks/roadmap_implement_step.md`, `tests/roadmap/test_roadmap_implement_prompt.py`. Changes: `src/devops_cli/ai/tasks/roadmap_implement_step.md`, `tests/roadmap/test_roadmap_implement_prompt.py`.

- [x] 3.1 Write failing tests: the prompt drops the rules that `AGENTS.md` and the routed documents own, names the heading of the rules section, and every `.data/` path of the prompt is a `.data/` path of `AGENTS.md` (the scratch directory is equal in both)
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_prompt.py` fails on the base
- [x] 3.2 Shrink the prompt to the runner facts and tell the agent where the rules are
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_prompt.py tests/roadmap/test_roadmap_implement_step.py tests/roadmap/test_roadmap_implement_shell_refusal.py tests/roadmap/test_roadmap_stage_kind.py`

## 4. Documents and the measured cost

Reads: `src/devops_cli/lang/en/help.py`, `src/devops_cli/config/settings.py`. Changes: `src/devops_cli/lang/en/help.py`, `src/devops_cli/config/settings.py`, `README.md`, `docs/CLI_REFERENCE.md`, `docs/commands/roadmap.md` and `docs/ENV_VARS.md`.

- [x] 4.1 Change the help text of `devops roadmap implement` and the description of `roadmap.stage.step_tokens`, then regenerate the documents
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops ci docs`
- [x] 4.2 Measure the tokens that the rules add to the step of three real groups of the corrected plans of #2175, #2462 and #2531, as the difference between the message on `origin/main` and on this branch
  - Verification: a repeatable manual check. On `origin/main` and on the branch, build the inputs of group 1 of each of the three changes with `build_step_inputs`, print `inputs.tokens`, and subtract. Each result stays under the step budget of 40,000 tokens

## 5. Fail-to-pass and archive

- [ ] 5.1 Run the fail-to-pass check on the new tests
  - Verification: `uv run devops ci fail-to-pass --base origin/main`
- [ ] 5.2 Archive the change
  - Verification: `uv run devops openspec archive 3097-step-gets-agents-md` and `uv run devops openspec check`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
