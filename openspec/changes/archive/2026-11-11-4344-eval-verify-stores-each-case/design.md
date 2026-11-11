# Design

## Decisions

- **The hook of the library gives each case.** `_run_cases` passes a `CaseLifecycle` subclass to `evaluate_sync`. Its `teardown` turns the `ReportCase` or `ReportCaseFailure` of the case into a `CaseOutcome` and gives it to `evaluate_cases`. A `None` result, from a stop in the case, gives nothing. After rejected credentials, no case is given, so the file holds the cases that ended before the rejection.
- **The score comes from the outcomes.** `verify_score(model, cases, outcomes)` matches the findings of each outcome to the defects of its case (`matched_defects`) and sums the rows, the serious defects and the cases. The same function scores a partial run, a resumed run and a full run. A case with no outcome counts as `not run`, as before.
- **The caller writes the file.** `evaluate_cases` takes `store`, a callable that gets the score of the cases that ended, at the start and after each case. The command writes `verify_json` of that score with `write_text_file`, which writes a temporary file in the same folder and then `os.replace`. A stop in a write leaves the earlier complete file.
- **A resume updates its file in place.** A normal run writes a new file with the time stamp of its start. A run with `--resume` writes to the file that the option names, so one file holds the whole run and a second stop can resume from the same path.
- **A resume reruns failed cases.** A case with a non-empty `error` in the report runs again, as does a case that the report lacks. The other cases of the report keep their outcomes.
- **A resume keeps every case of its report.** The cases of a resumed run are the cases that `--case` and `--limit` select and the cases of the report, in the order of the set. A smaller selection therefore does not drop a case from the file.
- **A resume refuses what it cannot merge.** The model of the report must be the model of the run, because the scores of two models must not mix. A case of the report that the set lacks has no labeled defects to score, so the command stops and names it. A file that does not validate as a report stops the command with its path. Each of these is a `ConfigurationError`, so the command prints one error line and exits 1 before any model call.

## Rejected alternatives

- **Store the case from a `try/finally` in the task.** The task does not know the error text that the library records (`ReportCaseFailure.error_message`), and it ends before the case is scored. The library already offers `CaseLifecycle.teardown` for this point of a case.
- **Run `evaluate_sync` once for each case.** It builds one dataset for each case, and it gives up the one run of the library for the set. The lifecycle hook gives each case with one run.
- **Patch or subclass `Dataset`.** It couples the project to internals of the library. The lifecycle hook is a public argument of `evaluate_sync`.
- **Append one JSON line for each case.** It adds a second format and needs a merge step to build the report. A full atomic rewrite keeps `verify_json` as the one format, and `devops roadmap eval screen --reviewer` reads every stored file as before.
- **Keep the evaluator `Recall` and read its scores.** A stored report holds the findings of each case and not the scores of the library, so a resumed case needs the score from its findings anyway. One function (`verify_score`) for both kinds of case keeps one rule.
- **Merge the reports of parallel processes.** It needs its own rules for duplicate cases and mixed models, and the issue asks for store and resume only. `--case` still splits the set between processes, and each process resumes its own file.
