# Tasks

## 1. The guard: `devops ci job-time`

- [ ] 1.1 Add failing tests in `tests/test_ci_job_time.py` over the fake of the GitHub API with the recorded runs of `main` in `tests/fixtures/github/ci_runs_main.json`: the job time read from the right job of each run, the stop at the wanted runs, a run without the job and a failed job left out, a second page of runs, the mean on the limit and over it, a short read, the options, the dry run, and the shape of the `job-time` job in `ci.yml`
  - Verification: `uv run devops ci test tests/test_ci_job_time.py` fails on the base
- [ ] 1.2 Add `GitHubClient.get_job_run_times`, the report in `ci/job_time.py`, the command `devops ci job-time` with its messages and help, and the job `Test Job Duration` in `ci.yml`. Register the command as not exposed by MCP and the step in the allowlist of the workflow parity test
  - Verification: `uv run devops ci test tests/test_ci_job_time.py tests/test_ci.py tests/test_mcp.py`
- [ ] 1.3 Run `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci docs`

## 2. The cut: work that every test repeated

- [ ] 2.1 Measure the job on the runner (24 runs) and the test run on 4 pinned CPUs, and write `baseline.md`
  - Verification: `baseline.md` holds the table of runs and the mean of the newest 10
- [ ] 2.2 Set `tmp_path_retention_policy = "failed"`, make the runtime directory of `isolate_session_bus` with `mkdtemp` inside one directory for each worker, and key the Markdown parse of `tests/support/markdown_examples.py` by the text of the document
  - Verification: `uv run devops ci test tests/test_k8s_llm_gateway.py tests/test_docs.py`
- [ ] 2.3 Build the LLM response cache on first use in `isolate_llm_response_cache`
  - Verification: `uv run devops ci test tests/test_llm_response_cache.py`
- [ ] 2.4 Raise the young threshold of the garbage collector and freeze the collected heap in the root conftest
  - Verification: `uv run devops ci test tests/test_memory_profiler.py`
- [ ] 2.5 Poll the shutdown of the five test servers every 0.01 s
  - Verification: `uv run devops ci test tests/test_sandbox_probe.py tests/test_sandbox_metrics.py tests/k8s/test_kubernetes_contract.py`
- [ ] 2.6 Show that the same tests run and the same lines are covered: the number of tests, the coverage total and the thresholds before and after
  - Verification: `proposal.md`, section "Result"
- [ ] 2.7 Add the section "Run time" to `docs/TESTING.md`
  - Verification: `uv run devops ci docs`

## Workflow follow-up

- The mean over ten runs on the runner is known only after the change merges and ten pushes to `main` have run. `devops ci job-time` states it. #2699 stays open until it reads under 300 s.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
