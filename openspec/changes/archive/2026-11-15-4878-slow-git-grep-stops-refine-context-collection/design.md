# Design

## Decisions
- Catch `subprocess.TimeoutExpired` in `git_result`: return exit code 124 and log a warning message. This prevents unhandled timeout exceptions across all git helper operations.
- Catch `subprocess.TimeoutExpired` in `_collect_identifiers`: treat a timeout as zero hits for that identifier, log a warning, and proceed to the next identifier.
- Add negative pathspecs `:(exclude)openspec/changes/archive` and `:(exclude)tests/fixtures`: avoid searching large historical change folders and fixture files during identifier lookup.
- Add `--max-count=5` flag to `git grep`: stop searching a file after five hits to reduce execution time.

## Rejected alternatives
- Increase timeout beyond 15 seconds: rejected because blocking on slow searches degrades job performance and delays other candidate items.
- Remove identifier grep entirely: rejected because cited identifier search provides valuable cross-referencing context for model planning.
