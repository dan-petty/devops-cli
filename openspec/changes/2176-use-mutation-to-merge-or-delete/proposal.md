# Proposal

## Why

The 2026-10-24 coverage audit of #2176 found 26 test files that cover no line of `src/` that another file does not also cover, and line coverage cannot show that such a file adds no check, because a file can assert something that no other file asserts. Mutation runs decide each file: a file that kills no mutant of its own adds no check. The table is the tree of b170358e, so the plan settles every row against this tree before it campaigns.

## What Changes

- Add a `## Mutation decisions` section to `docs/TESTING.md` with one row for each of the 26 table rows: the path at this commit, the campaign command, the duration, the killed and own mutant counts, and one decision.
- Add `tests/invariants/test_mutation_decisions.py` as the census of the 26 rows, which parses the section and fails on a row with no decision.
- Point the mutation test selection of `pyproject.toml` at the modules of this tree, add `openspec` to its copy list, and add `tests/invariants/test_mutmut_selection.py`.
- Campaign the seven AI rows with the whole suite and again with each file left out, fill their rows, and add their record check to the census test.
- Campaign the three configuration rows, move each distinct case that no other test asserts into `tests/config/test_config_key_removal.py` or `tests/config/test_config_file_that_is_not_yaml.py`, fill their rows, and add their record check.
- Campaign the six core, HTTP, language and Valkey rows, settle each of them, fill their rows, and add their record check.
- Campaign the six docs, benchmark, analyze and audit rows, settle each of them, fill their rows, and add their record check.
- Record the gate result, the total line coverage and the `fail_under` value in the record.
- Record the `Tests & Coverage` duration of the pull request beside the duration of the base run.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `mutation-run-selection`: The mutation selection names test paths of this tree, The mutation run copies the living specs

### Modified Capabilities

None.

## Impact

- Code: `pyproject.toml`
- Documents: `docs/TESTING.md`
- Tests: `tests/invariants/test_mutation_decisions.py`, `tests/invariants/test_mutmut_selection.py`, `tests/ai/client/test_ai_client_credentials.py`, `tests/ai/client/test_ai_gateway_base_url.py`, `tests/ai/test_ai_client_style_request.py`, `tests/ai/test_ai_task_loader.py`, `tests/ai/test_pydantic_ai_format_prompt.py`, `tests/ai/spend/test_ai_spend_dispatch.py`, `tests/ai/retries/test_pydantic_ai_retries.py`, `tests/config/test_settings_cache.py`, `tests/config/test_headless_auth.py`, `tests/commands/test_config.py`, `tests/config/test_config_key_removal.py`, `tests/config/test_config_file_that_is_not_yaml.py`, `tests/core/test_cleanup_fuzzing.py`, `tests/core/test_third_party_telemetry.py`, `tests/core/test_consolidation_binaries.py`, `tests/http/test_http_async_client.py`, `tests/lang/test_language_catalogs.py`, `tests/valkey/test_valkey_cache_tier.py`, `tests/docs/test_exceptions.py`, `tests/ai/benchmark/test_data_dir_configuration.py`, `tests/ai/analyze/test_ai_init.py`, `tests/commands/test_openspec_scaffold.py`, `tests/commands/test_cli_format_adoption.py`, `tests/commands/test_dependency_audit.py`

## Feasibility

- Probes: "The path `tests/commands/test_config.py` is a file of the staging commit." and "The path `tests/core/test_cleanup_fuzzing.py` is a file of the staging commit." Those two table rows name files of this tree.
- Probes: "The path `tests/test_agent.py` is no file of the staging commit. Commit 513bb31f2 2026-10-30 test(cli): tests mirror package directories and trim root conftest (#2830) deleted or renamed it." So the table is the tree of b170358e, and a row whose path no file holds is settled rather than campaigned.
- Probes: "The path `tests/test_ai_client_credentials.py` is no file at the root of the staging commit. These files of the commit are candidates: `tests/ai/client/test_ai_client_credentials.py`."
- `list_files("tests/config")` and `list_files("tests/commands")` show `tests/config/test_settings_cache.py`, `tests/config/test_headless_auth.py` and `tests/commands/test_config.py`, and `list_files("tests/telemetry")` shows `tests/telemetry/test_telemetry_collector_export.py`.
- `list_files` of `tests/ai`, `tests/ai/client`, `tests/ai/spend`, `tests/ai/retries`, `tests/ai/benchmark`, `tests/ai/analyze`, `tests/core`, `tests/docs`, `tests/http` and `tests/valkey` shows the package path of every other campaign row.
- `references("test_rag_rrf")` answers "files 4, lines 4" and lists only files under `openspec/changes/archive/`; `references("test_rag_loopback_policy")` answers "files 2, lines 2" and lists only archive files; `references("test_pydantic_ai_toolsets")` answers "files 5, lines 7", lists four archive files and `docs/agent/archive/historical-phases-1-to-50.md`. No file of this tree holds those modules, so those three rows are settled rows, and the one hit outside the archive is the `references` entry with a reason.
- No tool counted the 26 rows, so the count is unverified: `tests/invariants/test_mutation_decisions.py` is the census, it is the `verify` of group 1, and group 1 stops when it counts a number other than 26 or a campaign row whose path is no file of this tree. The record gives each of the 26 rows one decision of `kept`, `deleted`, `moved` or `settled`, and a row with no decision fails the census.
- The constant `CONST_OPENSPEC_SPECS_DIR` is `openspec/specs`, from `src/devops_cli/config/constants.py:5407:CONST_OPENSPEC_DIR: Final[str] = "openspec"` and `src/devops_cli/config/constants.py:5415:CONST_OPENSPEC_SPECS_DIR: Final[str]`. `tests/openspec/test_openspec_new.py:243:real_spec = REPO_ROOT / CONST_OPENSPEC_SPECS_DIR` reads a real spec of that folder, and `pyproject.toml:315:also_copy = [` holds no `openspec` entry, so the stats run fails before group 2 adds it.
- `tests/invariants/test_living_specs.py:34:for path in sorted(_SPECS.rglob("spec.md"))` yields no path when the folder is absent, so that test passes without the copy; the test that needs the copy is `tests/openspec/test_openspec_new.py:243:real_spec = REPO_ROOT / CONST_OPENSPEC_SPECS_DIR`.
- `pyproject.toml:298:--ignore=tests/test_architectural_invariants.py` names a module of the old root-level tests folder that no file of this tree holds, so the invariant module now runs inside the mutants tree against mutmut's generated code and fails; group 2 points each selection entry at the module that holds it at this commit.
- `pyproject.toml:265:fail_under = 85` is the floor that group 7 keeps, and `docs/TESTING.md` is the page that gains the record.
- The first review finding is fixed: `file_symbols("tests/config/test_config_key_removal.py")` lists `tests/config/test_config_key_removal.py:def test_a_removal_of_a_credential_leaves_no_file_that_holds_its_value` and `def test_a_dry_run_of_a_credential_removal_shows_the_placeholder_not_the_value`, and `file_symbols("tests/config/test_config_file_that_is_not_yaml.py")` lists its config-file error case, so group 4 now names both modules in `reads` and `changes`.
- The second review finding is fixed: the `verify` of group 4 runs the `tests/config` folder, so every case that moves into `tests/config/test_config_key_removal.py` or `tests/config/test_config_file_that_is_not_yaml.py` runs in that group.
- `read_file("tests/telemetry/test_telemetry_collector_export.py", 1, 45)` gives `tests/telemetry/test_telemetry_collector_export.py:1:"""devops-cli telemetry reaches the cluster's collector, or says it does not (#547).`, so its subject is the telemetry collector and no configuration case moves into the file that the audit names as the covering file.
- The gate's own `uv audit`, `npm audit`, `uv tree --outdated` and `uv check` rows query the package indexes, so the plan states a network precondition for `uv run devops ci` and claims no offline run of the gate.
- Group 7 records only what the local gate shows, and group 8 reads the `Tests & Coverage` duration of the pull request, because no local command reports a pull request's job time.
- Each campaign group adds a test to `tests/invariants/test_mutation_decisions.py` and runs it as its `verify`, so a row with no command, duration, count or decision fails that group.
- Precondition of `uv run devops ci mutate <path>`: a checkout of the repository and the `mutmut==3.8.1` pin that the dev group of `pyproject.toml` holds; it reaches no network and writes `mutants/` in the checkout.
- Precondition of `uv run devops ci test <paths>`: a checkout of the repository; the tests reach no network and no cluster.
- Precondition of `uv run devops ci`: a checkout of the repository and a network, because its audit rows query the package indexes.
- Precondition of `gh pr checks` and `gh run view` in the process of group 8: a client of GitHub and a network.
- Programs: `devops`, `pytest` and `gh` are runner tools of the image and `mutmut` comes from the dev group, so no program of a group is `NOT_IN_RUNNER`; pod setting `readOnlyRootFilesystem: true` applies to each verify, and a campaign writes only `mutants/` in the writable checkout.
- Failure classes: a campaign that does not end is `timeout`, a run whose tests fail is `test`, and a row whose path no file holds is `premise_false`.
- First checks: `uv run devops ci test tests/invariants/test_mutation_decisions.py` fails before the record exists, `uv run devops ci test tests/invariants/test_mutmut_selection.py` fails on the first stale selection entry, and `uv run devops ci mutate src/devops_cli/core/coverage_index.py` completes a stats run before any campaign starts.
- The issue cannot be built as written for the four rows whose path no file of this tree holds; the record settles each of them with the commit that removed it, and the plan re-creates no deleted path.

## Existing Tool Considered

mutmut 3.8.1 is the pinned mutation tool, and `uv run devops ci mutate` runs it over the `src/` files a command names, with `[tool.mutmut]` in `pyproject.toml` holding its source paths, its test selection and its copy list. The change adds no harness of its own.

## Dependencies

None.
