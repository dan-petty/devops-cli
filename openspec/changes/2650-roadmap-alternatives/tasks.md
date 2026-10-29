# Tasks

## 1. The store reads the facts of a repository

- [ ] 1.1 Write a contract test for `repository_facts` in `tests/test_roadmap_store_contract.py` (both adapters: a repository with a release, a repository with no release, a missing repository) and a GitHub adapter test in `tests/test_roadmap_github_store.py` (the two `gh` arguments), and verify that `uv run devops ci test tests/test_roadmap_store_contract.py tests/test_roadmap_github_store.py` fails because the store has no `repository_facts`
- [ ] 1.2 Add `RepositoryFacts` and `RoadmapStore.repository_facts` in `src/devops_cli/roadmap/store.py`, the GitHub adapter and its argument builders in `src/devops_cli/roadmap/github_store.py`, the in-memory adapter with `seed_repository` in `src/devops_cli/roadmap/memory_store.py`, and the fake's routes in `tests/roadmap_github_fake.py`, and verify that `uv run devops ci test tests/test_roadmap_store_contract.py tests/test_roadmap_github_store.py` passes

## 2. Both jobs share the agent run

- [ ] 2.1 Write `test_the_alternatives_tools_run_in_the_same_agent_run` in `tests/test_roadmap_refine_investigation.py` (a tool set other than `InvestigationTools` runs through `investigate`, and the web search of `InvestigationTools` still adds each URL and stops at its cap), and verify that `uv run devops ci test tests/test_roadmap_refine_investigation.py` fails because `investigate` accepts only `InvestigationTools`
- [ ] 2.2 Move the web search body into `cited_web_search` and type the `tools` argument of `investigate` as a set of tools, in `src/devops_cli/roadmap/refine_investigation.py`, and verify that `uv run devops ci test tests/test_roadmap_refine_investigation.py tests/test_roadmap_refine.py` passes

## 3. The job selects, checks, validates and writes

- [ ] 3.1 Write `tests/test_roadmap_alternatives.py` for every requirement of the spec (selection and order, the tools and their limits, `maintained`, the refused reply, the writes and the second run, the off states, the record keys), with the scripted `FunctionModel`, `GitHubFake`-style GitHub, and `StubWeb` for Firecrawl and PyPI, and verify that `uv run devops ci test tests/test_roadmap_alternatives.py` fails because the module does not exist
- [ ] 3.2 Add the constants, the defaults and the setting `roadmap.alternatives.recheck_days` in `src/devops_cli/config/`, the record keys in `src/devops_cli/roadmap/store.py`, `RoadmapAlternativesError` in `src/devops_cli/exceptions/roadmap.py`, the messages in `src/devops_cli/lang/en/messages.py`, the prompt `src/devops_cli/ai/tasks/roadmap_alternatives.md`, and `src/devops_cli/roadmap/alternatives.py`, and verify that `uv run devops ci test tests/test_roadmap_alternatives.py` passes

## 4. The command and the dry run

- [ ] 4.1 Write the command tests (modes, the plan output, the exit code after a skipped item, and a dry run that makes no request) in `tests/test_roadmap_alternatives.py` and `tests/test_roadmap_dry_runs.py`, and verify that `uv run devops ci test tests/test_roadmap_alternatives.py tests/test_roadmap_dry_runs.py` fails because the command does not exist
- [ ] 4.2 Add `devops roadmap alternatives` in `src/devops_cli/commands/roadmap.py`, its help text in `src/devops_cli/lang/en/help.py`, and `alternatives_requests` in `src/devops_cli/roadmap/request_plan.py`, and verify that `uv run devops ci test tests/test_roadmap_alternatives.py tests/test_roadmap_dry_runs.py` passes

## 5. Documentation

- [ ] 5.1 Add the term "Alternative" to `CONTEXT.md`, regenerate the documents with `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes
- [ ] 5.2 Run `uv run devops ci` once, fix any failure at its cause, and verify that it passes

## Workflow follow-up

- The Service row on the model lane, the metric and refine's use of the recorded verdict are sub-issue 2 of #2648.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
