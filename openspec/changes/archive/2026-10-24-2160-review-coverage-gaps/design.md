# Design

## Where a coverage gap goes

The orchestrator already keeps `errored_files`, a map from a file path to a reason. The report shows it in the table of skipped and errored files, in the executive summary and in the terminal summary. Each stage that cannot read a file adds the file to this map with the stage and the reason. Module functions, such as admission, get the map as the `coverage_gaps` argument, as they get `rejection_counts`. `_record_coverage_gap` adds a second reason of a file after the first, so a later stage does not erase the gap of an earlier stage.

The reason gives the `strerror` of the `OSError`, for example `Pre-analysis: Permission denied`. The text of the error itself names the absolute path of the file, and the report gives paths relative to the reviewed tree.

## Rejected alternatives

- **A new field for coverage gaps in `ReviewSessionPayload`.** The table of skipped and errored files already holds this data, and the issue names `errored_files` as the model. A second record would split one fact between two places.
- **A test that makes `list_repo_files` or `find_repo_root` fail.** The probe in the proposal shows that neither function raises for a path that the file system accepts. The only way to make one fail is to patch a `devops_cli` name, which docs/TESTING.md forbids. The handlers are deleted as dead code.
- **Catch `TypeError` in the cache check.** A cached time with no time zone made the comparison with an aware file time raise `TypeError`. The check now treats such a time as a cache miss, and compares `st_mtime` with the cached time as numbers, so no comparison raises.
- **Make a file that pre-analysis could not prepare (`stat` fails) a coverage gap.** `_pre_analysis_candidates` keeps only files for which `is_file()` is true just before, so `stat` fails only when the file is deleted during the review. The base code raised that error at the first `stat` of the loop, outside the handler, and this change keeps that.
