# Design

## Decisions

- **Measure first, then pick the lever.**: The issue asks for the change with the largest measured share, so the plan does not name the lever before the numbers exist. Group 1 measures. Group 2 picks from the table below. Group 3 applies one row.
- **Measure CPU time, not wall time.**: The shell `time` of the controller counts the user and system time of its worker children. Wall time moved from 3 m 28 s to 6 m 27 s on one suite when the host was loaded (#2356). CPU time moves less.
- **Measure a plain run, `uv run pytest`.**: The coverage cost is the work of #2373. A plain run keeps this change apart from it. `--cov` stays out of both the before and the after runs.
- **Keep the measuring plugin out of git.**: It is a scratch file of about 40 lines. Nothing in the repository reads it. A committed plugin would be a tool to keep for one measurement.
- **Stop when no candidate can reach 5%.**: AGENTS.md rule 2 says to write no compensating code when the premise fails. If the numbers of group 1 show that no row of the table can lower the CPU time of a full run by 5%, group 2 stops. The implementer then returns the item to New with the figures: `uv run devops roadmap return 2371 --comment "<figures>" --confirm`.

## Candidates

| Candidate | Files it changes | Evidence now | Share to compute |
| :--- | :--- | :--- | :--- |
| Fewer workers than CPUs on the 4-CPU runner (`-n 3`, `-n 2`) | `.github/workflows/ci.yml` or `pyproject.toml` (`addopts`), and the pin in `tests/commands/test_test_selection.py` when `addopts` changes | Each worker collects the whole suite in about 19 s of CPU time, so N workers spend N times that. | CPU time of one collection times the workers removed, against the total CPU time. The wall time of the job must not rise. |
| Shorter collection | `tests/conftest.py`, `tests/support/`, or the top-level imports of the test modules | The profile of one collection spends the most self time in `_matchfactories` and `process_argname`, which build the fixture closure of 15,801 tests. Imports are about 3 s of 19 s. | CPU time of one collection saved, times the number of workers. |
| Preload fixture for the heavy modules | none | Rejected. `pydantic_ai`, `anthropic`, `kubernetes` and `textual` are in `sys.modules` after collection. A fixture moves an import and cannot lower the total CPU time. | none |

## Rejected alternatives

- **A session fixture that imports `pydantic_ai`, `anthropic`, `kubernetes` and `textual`.**: The collection of every worker already imports them (see Feasibility in `proposal.md`). The fixture is a no-op for them. For a module that is not in `sys.modules` after collection, the fixture adds the import to every worker, also to a worker that would never import it. The issue says it itself: a test that carries the import cost moves it to the next test when the test goes.
- **A spec delta on `ci-job-time`.**: That capability is the command `devops ci job-time`. A change to the test suite alters nothing that command does.
- **A new test for the chosen change.**: The change is a setting or a refactor of the test suite with no new behavior. Its check is the CPU time of three runs and the green suite.
