# Task: A One-File Path Review Spends No Minutes on Ignored Trees or a Cold mypy Cache (#2034)

**Issue**: [#2034](https://github.com/dan-petty/devops-cli/issues/2034)
**Scope**: scope/review
**Feasibility**: On 2026-10-24, `detect_manifest_coverage_gaps` over the owner's checkout took 684.6 s at a load average of 82 and found 0 gaps. It walked every file with `rglob`, which includes the ignored `.data/` tree with about 15 agent worktrees and their environments. `git ls-files --cached --others --exclude-standard` lists the 2,328 files of the same checkout in 0.07 to 0.2 s. `list_repo_files` took 2.3 to 2.6 s for those files at a load average of 115: the git call took 0.2 s, and a full `resolve()` and `is_file()` of each file took the rest. The 30.7 s in the cProfile run of the issue is not a real wall time: the profile mixes the threads, and it names `_send_payload_sync`, which runs on an export thread, as the caller of `run_mypy_scan`. `run_mypy_scan` gave mypy a new `TemporaryDirectory` as its cache on each run. mypy 2.3.1 keeps its incremental cache in SQLite (`sqlite_cache = True`), which lets one process write at a time. `tracer.flush` waits at most `DEFAULT_OTEL_DRAIN_TIMEOUT_SECONDS` (1 s), and the exports run on a background executor with timeouts of 1 s.

## Description

The lockfile coverage check of a review, and an osv-scanner run that names no lockfile, read the files that git lists for the tree, tracked or not, through `list_repo_files`. An ignored tree, such as a virtual environment or the data directory, neither adds a gap nor hides one. The git listing of `list_repo_files` resolves each directory once and does one `lstat` for each file. It resolves a file in full only when the file is a link, so a file outside the checkout stays out of the list.

mypy in a review uses a cache that stays between reviews, in `<data.cache_dir>/mypy/<key>`. The key holds the reviewed tree, the Python version and the digest of the `uv.lock` of the environment that runs mypy. `resolve_data_path` puts the cache under the user data root while a review runs from a repository other than devops-cli's own, so a reviewed tree never supplies it (#972). Runs over one tree take turns on an exclusive lock beside the cache.

## Acceptance Criteria

- [x] `tests/test_osv_scanner.py::test_lockfile_coverage_reads_only_the_files_git_lists` and `::test_osv_scanner_takes_no_lockfile_from_an_ignored_tree` fail on the base and pass after the change.
- [x] `tests/test_review_ruff_mypy_evidence.py::test_mypy_runs_over_one_tree_share_a_cache_in_the_data_directory` fails on the base and passes after the change.
- [x] `tests/test_repos.py::test_repo_files_stay_inside_the_checkout_through_links` passes on the base and after the change: a tracked directory that the working tree replaced with a link to outside the checkout stays out of the list.
- [x] After the change, `detect_manifest_coverage_gaps` over the owner's checkout takes 0.47 s and finds the same 0 gaps.
- [x] Live `devops ai review path src/devops_cli/core/dns_names.py` at load averages of 25 to 60, with 0 model calls: 6 min 12 s with an empty mypy cache, of which the mypy run took 293 s. The next run took 2 min 9 s, of which the mypy run took 10.9 s. In both traces, each lockfile coverage check and git listing took less than 0.4 s.
- [x] The trace export does not block the command: in a py-spy record of the second run (129.5 s of main-thread samples), `tracer.flush` and `shutdown` hold 0.1 s and the thread joins at exit hold 0.1 s.

## Deliverables

- [x] The lockfile coverage check and the osv-scanner lockfile search read the files that git lists.
- [x] The git listing of `list_repo_files` resolves each directory once.
- [x] mypy in a review keeps its cache in the data cache directory, keyed by the reviewed tree, the Python version and the environment lock.
