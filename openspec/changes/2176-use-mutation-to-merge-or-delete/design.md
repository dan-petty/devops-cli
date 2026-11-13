# Design

## Decisions

- **Settle each of the 26 table rows against this tree before any campaign**: The table is the tree of b170358e: the probes show that `tests/test_agent.py` is no file of this commit, and a campaign on a path that no file holds decides nothing.
- **Repair the mutation test selection and the copy list inside this change**: `pyproject.toml:298:--ignore=tests/test_architectural_invariants.py` names a path that no file of this tree holds, so the module it meant to leave out runs against mutmut's generated code; `pyproject.toml:315:also_copy = [` holds no `openspec` entry, and `tests/openspec/test_openspec_new.py:243:real_spec = REPO_ROOT / CONST_OPENSPEC_SPECS_DIR` reads a real spec, so the stats run fails until both are repaired.
- **Attribute a mutant to a file with two runs of the same mutants**: mutmut 3.8.1 keeps no record of the test that killed a mutant, so a mutant that the whole suite kills and the run without the file leaves alive is the file's own.
- **Keep the record in `docs/TESTING.md`**: A task group may not write a path of the plan's own change folder, and the testing guide is already a page of the docs site, so no navigation entry is needed.
- **Move a configuration case into the mirror module of its subject, not into the audit's covering file**: `tests/telemetry/test_telemetry_collector_export.py:1:"""devops-cli telemetry reaches the cluster's collector, or says it does not (#547).` names the telemetry collector as its subject, and `tests/config/test_config_key_removal.py:def test_a_removal_of_a_credential_leaves_no_file_that_holds_its_value` holds the credential removal case, so a configuration case belongs in `tests/config/`.
- **Check the record with an invariant test in each campaign group**: Each campaign group adds its own test to `tests/invariants/test_mutation_decisions.py` and runs it as its `verify`, so a row that holds no command, no duration, no counts or no decision fails the group that fills it.
- **Read the `Tests & Coverage` duration with a person's step, not a command**: `devops ci job-time` reads push runs of `main`, and no local command reports a pull request's job time, so group 8 gives the steps that read the check run of the pull request and of the base run.
- **Keep every guard test, contract suite and invariant test**: The issue forbids deleting a contract suite or an invariant test, and a mutation count does not see a guard test, so no file under `tests/invariants/` and no contract suite is deleted.
- **Take a new capability for the mutation selection**: The capability `ci-test-selection` covers the path arguments of `devops ci test` only, and no capability holds a rule for the tests that the mutation run selects.
- **Leave `docs/agent/archive/historical-phases-1-to-50.md` unchanged**: `references("test_pydantic_ai_toolsets")` names it, and it is a historical record of past phases that no test and no command reads, so the settled row changes no line of it.

## Rejected alternatives

- **Delete the files on the line-coverage audit alone**: The issue states that a file can cover a line and still assert what no other file asserts, so line coverage cannot show that a file adds no check.
- **Run the campaign against the paths of the table**: The probes show that `tests/test_agent.py` and `tests/test_ai_client_credentials.py` are no files of this commit, and commit 513bb31f2 deleted or renamed them.
- **Move the configuration cases into `tests/telemetry/test_telemetry_collector_export.py`, the covering file of the audit**: Its first line names the telemetry collector as its subject, and `tests/config/test_config_key_removal.py` and `tests/config/test_config_file_that_is_not_yaml.py` already hold the removal and config-file error cases, so a configuration case there would sit in the wrong package.
- **Write the mutation record into the change folder of the item**: A task group may not change or create a path of the plan's own change folder under `openspec/changes/`, because the job writes that folder before the groups run.
- **Build a harness that records which test killed each mutant**: mutmut 3.8.1 is pinned and `devops ci mutate` runs it; a harness would cost tokens to write, keep and fix, and would copy the tool.
- **Leave the mutation selection as it is and run the campaigns**: The selection names modules of the old root-level tests folder, so the modules it meant to leave out run inside the mutants tree against mutmut's generated code and the stats run fails.

## Unchanged references

- `docs/agent/archive/historical-phases-1-to-50.md` (quoted target): A historical record of past phases that no test and no command reads, so the settled toolsets row changes no line of it.

## Security

The mutation run copies the repository into `mutants/` and runs the suite there, and this change adds `openspec` to that copy list, so the living specs enter the copy and nothing else does; the specs hold requirement text and no secret. A person must confirm that the copy list still holds no keyring file, no environment file and no installation token, and that no selection entry leaves the tree. `tests/invariants/test_mutmut_selection.py` fails if an entry names a path outside the tree or the copy list drops `openspec`.
