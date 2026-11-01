# Design

## Decisions

- **Measure with mutmut through the existing `devops ci mutate` setup.** The tool, its `[tool.mutmut]` table and its 4-hour command timeout exist. The change adds no code. Building a harness would cost tokens to write, keep and fix, and would copy a maintained tool.
- **Attribute a mutant to a file with two runs of the same mutants, as the issue proposes.** mutmut 3.8.0 keeps no record of which test killed a mutant. The first run uses the whole suite. The second run leaves the file out. A mutant that the whole suite kills and the second run does not kill is the file's own.
- **Run only the mutants of the functions a file runs.** A file can kill a mutant only in a function it runs. `mutants/mutmut-stats.json` lists the tests that run each function, so the list of functions is exact and costs no coverage run.
- **Leave a file out with `PYTEST_ADDOPTS="--deselect=<file>"`.** `pytest.main` reads it in the mutmut process (see Feasibility in `proposal.md`). The `[tool.mutmut]` table in `pyproject.toml` stays unchanged.
- **Decide the files of a group one by one, in the order of the task.** When two files check the same thing, each has no own mutant while the other is in the suite. If both were deleted, the check would be lost. So the run for a file also leaves out every file that an earlier step of the same group marked for deletion.
- **Keep the record in the change folder.** `mutation-report.md` is archived with the folder under `openspec/changes/archive/`. A pull request comment would not travel with the repository.
- **A file with no own mutant is deleted.** The project is before 1.0 and keeps no old path ([AGENTS.md](../../../AGENTS.md)). A test moves only to hold the line coverage (group 10).

## Method

For each file F of a group, in the order of the group:

1. **Functions.** List the functions that F runs: `jq -r --arg f "<F>::" '.tests_by_mangled_function_name | to_entries[] | select(.value | any(startswith($f))) | .key' mutants/mutmut-stats.json`. The first command that builds `mutants/` is `uv run devops ci mutate <one src file>` (group 1). Later groups reuse `mutants/`.
2. **Whole suite.** Run the mutants of those functions: add `__mutmut_*` to each name and pass the names to `uv run mutmut run`. Leave out the files that earlier steps of the group marked for deletion (`PYTEST_ADDOPTS`, as in step 4). Save `uv run mutmut results --all true` to `.data/agent/scratch/2162/<file>-whole.txt`. The mutants with status `killed` are the killed set K. Write the count of K in the report.
3. **Functions that only F runs.** A function whose tests all sit in F, or in files already marked for deletion, has no test without F. Its mutants are the file's own. Do not rerun them: pytest ends with exit status 5 when it selects no test, and mutmut then stops.
4. **Without the file.** Run the mutants of K again, with `PYTEST_ADDOPTS="--deselect=<F> --deselect=<earlier file> ..."`. An explicit mutant name runs again. Read `uv run mutmut results --all true`. A mutant of K with status `survived` is not killed without F. It is the file's own mutant. Write the names in the report.
5. **Verdict.** No own mutant: the verdict is `delete`, and the file joins the exempt check below. One or more own mutants: the verdict is `keep`, and the report names the mutants.

The report has one row per file: `| path | functions | mutants killed (whole suite) | own mutants | verdict |`. The own mutants of a kept file are listed under the table.

**Exempt files.** A contract suite (its name holds `contract`), an invariant test (it sits in `tests/invariants/`) and a test of a security guard are never deleted. A security guard is a check that refuses or masks unsafe input, such as egress, secret, sandbox or injection checks ([SECURITY.md](../../../SECURITY.md)). The report states, for each file with verdict `delete`, that it is none of the three. The files in `tests/security/` of this change test the parse and report of a scanner, not a guard, but the group reads the file before it says so.

**Stop rule.** If the stats run of group 1 does not end in one command, or one `uv run mutmut run` of a group does not end inside 14400 s after it is split by file, the premise fails. Write no workaround. Return the item with `uv run devops roadmap return 2162 --comment "<numbers>" --confirm`.

## Files and covering files

The covering file of a row is where a case moves if group 10 needs it. Paths are the paths on `main` today.

| File | Tests | Covering file (issue) |
| :--- | ---: | :--- |
| `tests/ai/review/test_cited_code.py` | 2 | `tests/review/test_review_group_analysis.py` |
| `tests/commands/test_review.py` | 2 | `tests/commands/test_review_adjudication.py` |
| `tests/commands/test_review_removed_options.py` | 1 | none named |
| `tests/ai/personas/test_custom_personas.py` | 3 | none named |
| `tests/ai/test_review_advisory_backing.py` | 1 | none named |
| `tests/ai/review/test_review_deduplication.py` | 4 | `tests/ai/review/test_review_pipeline.py` |
| `tests/ai/review/test_review_defects_comments.py` | 1 | none named |
| `tests/ai/review/test_review_defenses_and_verification.py` | 7 | `tests/security/test_review_tool_runs.py` |
| `tests/ai/review/test_review_history.py` | 6 | `tests/review/test_review_group_analysis.py` |
| `tests/ai/test_review_location_paths.py` | 5 | none named |
| `tests/ai/test_review_loop_hardening.py` | 5 | none named |
| `tests/ai/review/test_review_regression_harness.py` | 2 | `tests/ai/test_review_finding_losses.py` |
| `tests/ai/review/test_review_taxonomy_and_severity.py` | 7 | none named |
| `tests/ai/test_review_verification.py` | 8 | `tests/ai/review/test_review_runner.py` |
| `tests/ai/test_structural_positional_oracles.py` | 3 | none named |
| `tests/security/test_security_kubelinter.py` | 8 | `tests/security/test_sarif_emission.py` and `tests/security/test_sarif_ingestion.py` |
| `tests/security/test_sarif_fuzzing.py` | 5 | none named |

Where the issue names no covering file, group 10 picks the file of the same behavior in the mirror directory of the source module (`docs/TESTING.md`, Layout), found with `git grep` for the function names in the report, and the report says which file it picked.

## Rejected alternatives

- **Keep the 18 files and trust line coverage.** The issue gives the reason: a file can run a line and assert something no other file asserts. The overlap numbers are also stale (see `proposal.md`, Feasibility).
- **Mutate all 79 modules of the 17 files in one command.** The union of the files runs 604 functions outside the 114 that every file runs, in 79 modules. The mutants of the large files (`test_review_history`: 307 functions in 44 modules) alone could pass the 14400 s timeout of one command. Groups with one run per file keep each command inside the timeout, and `mutants/` keeps the finished mutants for the next run.
- **Write a script that finds the killing test of each mutant.** mutmut 3.8.0 does not report it (its own source holds a TODO for it). A script would copy the runner of a maintained tool. The two-run method gives the same answer with the tool as it is.
- **Change the `pytest_add_cli_args_test_selection` list in `pyproject.toml` for each file.** mutmut hashes that list as `test_selection` in its config fingerprint (`mutmut/configuration.py`: "a change reshapes the stats mapping"), so the edit can force a new stats run, which is a serial run of the whole suite. `PYTEST_ADDOPTS` is not part of the fingerprint.
- **Keep the report only in the pull request.** A pull request comment is not in the repository after the merge. The report in the change folder is.
