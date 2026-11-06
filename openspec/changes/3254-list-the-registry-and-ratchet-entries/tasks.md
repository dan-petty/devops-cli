# Tasks

## 1. Read the registry declarations of the test modules

Reads: `src/devops_cli/roadmap/stage_change.py`, `tests/roadmap/test_roadmap_limit_classes.py`. Changes: `src/devops_cli/roadmap/stage_registry.py` (new), `tests/roadmap/test_roadmap_stage_registry.py` (new).

- [ ] 1.1 Write `tests/roadmap/test_roadmap_stage_registry.py::test_a_declaration_enters_the_table_with_its_path_and_line` first: a module holding a `REGISTRY_COUNTS` literal gives one entry with its token, its kind, its declared path and its line
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_registry.py` fails on the base
- [ ] 1.2 Add `src/devops_cli/roadmap/stage_registry.py` with a `RegistryCount` record of `kind`, `token` and `path`, a `counts_in(path)` reader that parses one module with `ast` and reads the module-level `REGISTRY_COUNTS` tuple of literals, and a `registry_table(root)` builder that walks the modules under the tests directory and returns each entry with `path:line`. Import no test module. The test writes a temporary module and reads it back
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_registry.py` passes

## 2. Declare what each registry test counts

Reads: `tests/roadmap/test_roadmap_limit_classes.py`, `tests/support/fakes/roadmap_store.py`, `tests/telemetry/test_telemetry_instruments.py`, `tests/roadmap/test_roadmap_dry_runs.py`. Changes: `tests/roadmap/test_roadmap_limit_classes.py`, `tests/support/fakes/roadmap_store.py`, `tests/telemetry/test_telemetry_instruments.py`, `tests/roadmap/test_roadmap_dry_runs.py`.

- [ ] 2.1 Add a module-level `REGISTRY_COUNTS` tuple to each of the four test modules. `tests/roadmap/test_roadmap_limit_classes.py` declares the `CONST_ROADMAP_` and `DEFAULT_ROADMAP_` constant prefixes. `tests/support/fakes/roadmap_store.py` declares the `WRITES` table. `tests/telemetry/test_telemetry_instruments.py` declares the `INSTRUMENTS` table and the `devops_cli_` metric prefix. `tests/roadmap/test_roadmap_dry_runs.py` declares `stage_requests` and `implement_requests`. Each entry names the path that must carry the entry: the declaring test, `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/roadmap/request_plan.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_limit_classes.py tests/telemetry/test_telemetry_instruments.py` passes

## 3. List the matching places in the plan context

Reads: `src/devops_cli/roadmap/stage_registry.py`, `src/devops_cli/roadmap/stage.py`, `tests/roadmap/test_roadmap_stage_plan.py`. Changes: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_registry.py`, `tests/roadmap/test_roadmap_stage_plan.py`, `docs/ROADMAP_WORKFLOW.md`.

- [ ] 3.1 Add to `tests/roadmap/test_roadmap_stage_plan.py` a case where a plan that adds `DEFAULT_ROADMAP_EXAMPLE_LIMIT` gets `tests/roadmap/test_roadmap_limit_classes.py` in its context
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` fails on the base
- [ ] 3.2 Add `matches(table, texts, paths)` to `src/devops_cli/roadmap/stage_registry.py`: it returns each entry whose token appears in the task texts or in a changed path, with `path:line`. Call it from `src/devops_cli/roadmap/stage.py` where the plan context is built, and add a `Registry places` section to that context. A plan that adds no counted item gets no section
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes
- [ ] 3.3 Update `docs/ROADMAP_WORKFLOW.md`, and run `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci docs` passes

## 4. Refuse a plan that misses a listed place

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_registry.py`, `tests/roadmap/test_roadmap_stage_plan.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `tests/roadmap/test_roadmap_stage_plan.py`.

- [ ] 4.1 Add to `tests/roadmap/test_roadmap_stage_plan.py` a case where a plan that adds a write method gets the dry-run test, the fault-test table, the contract test and the request-plan entry in its context and, with no task for the fault-test path, gets a problem naming it; and a case where a plan naming every listed place gets none
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` fails on the base
- [ ] 4.2 Extend `check_proposal` in `src/devops_cli/roadmap/stage_change.py`: for each matched entry, refuse when no task text of the plan names the declared path, and name the path and its declaring `path:line` in the problem
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes

## 5. Refuse a stale test path in a docstring or a spec

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_registry.py`, `tests/roadmap/test_roadmap_stage_form.py`. Changes: `src/devops_cli/roadmap/stage_registry.py`, `src/devops_cli/roadmap/stage_change.py`, `tests/roadmap/test_roadmap_stage_registry.py`, `tests/roadmap/test_roadmap_stage_form.py`.

- [ ] 5.1 Add to `tests/roadmap/test_roadmap_stage_registry.py` two cases: a spec text that names a test module the commit does not hold returns that name, and a docstring that names `tests/roadmap/test_roadmap_limit_classes.py` returns nothing
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_registry.py tests/roadmap/test_roadmap_stage_form.py` fails on the base
- [ ] 5.2 Add `missing_test_paths(root, texts)` to `src/devops_cli/roadmap/stage_registry.py`: it reads the test module names of each text, keeps the ones that name no file of the commit, and returns them sorted. Call it from `check_proposal` for the changed Python docstrings and the spec files of the change, and add each missing name to the refusal list
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_registry.py tests/roadmap/test_roadmap_stage_form.py` passes

## 6. Correct the stale test path in the telemetry doc

Reads: `docs/TELEMETRY.md`, `tests/telemetry/test_telemetry_instruments.py`. Changes: `docs/TELEMETRY.md`.

- [ ] 6.1 In `docs/TELEMETRY.md`, replace the sentence that names the old root-level telemetry test module with `tests/telemetry/test_telemetry_instruments.py`, and keep the rest of the paragraph on `INSTRUMENTS` as it is
  - Verification: `uv run devops ci docs` passes
- [ ] 6.2 Update `docs/TELEMETRY.md`, and run `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci docs` passes

## Criteria

- Group 3: A test shows that a plan that adds a `DEFAULT_ROADMAP_*` constant gets the limit-class ratchet in its context and is refused without a task for it.
- Group 4: A test shows that a plan that adds a job write gets the dry-run, fault-test and contract entries.
- Group 5: A test fails when a test path named in a docstring or a spec does not exist.
- Group 2: The table is derived from the tests (a marker or a named constant), not copied by hand.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
