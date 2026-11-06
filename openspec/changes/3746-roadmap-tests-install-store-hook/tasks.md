# Tasks

## 1. The install hook (new behavior, test first)

- [x] 1.1 Write `tests/roadmap/test_roadmap_store_install.py`, then add `install_roadmap_store` and `reset_roadmap_store` to `roadmap/store.py` and register the reset with the floor in `tests/conftest.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_store_install.py`
- [x] 1.2 The `roadmap_store` and `unreadable_github_roadmap` fixtures install through the hook, and `github_roadmap_factory` is gone
  - Verification: `! git grep -nF -e github_roadmap_factory -e roadmap_store_module -- src tests docs`

## 2. The fakes (test-only edits)

- [x] 2.1 Add the faults of the store fake and the new answers of the model fake, with their tests
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_store_fake.py tests/ai/client/test_model_contract.py`
- [x] 2.2 Move `GitHubFake` to `tests/support/fakes/github_repository.py` and add `GitHubFake.install`
  - Verification: `! git grep -nF -e roadmap_github_fake -- src tests docs`

## 3. The tests use the hook and the fakes (test-only edits)

- [x] 3.1 Move the refine, dry-run, intake, run and GitHub store tests and the milestone test to the hook and the fakes
  - Verification: `uv run devops ci test tests/roadmap tests/commands/test_github_milestones.py`
- [x] 3.2 Add `record_passing_run` to `ci/cache.py`, call it from the CI command, and move the CI cache tests onto it
  - Verification: `uv run devops ci test tests/ci tests/commands/test_ci.py`
- [x] 3.3 The nine files import no private name of `devops_cli`
  - Verification: `! git grep -nF -e _run_intake_adapter -e _run_metrics_adapter -e _run_refine_adapter -e _run_release_comments_adapter -e _try_save_ci_cache -e _worktree_divergent_paths -- tests/ci tests/roadmap/test_roadmap_run.py tests/roadmap/test_roadmap_intake.py tests/roadmap/test_roadmap_refine.py tests/roadmap/test_roadmap_dry_runs.py tests/roadmap/test_roadmap_github_store.py`

## 4. Documents

- [x] 4.1 `docs/TESTING.md` names the install hook, the fault mode and the repository fake, and the active plan of #3187 names the new path
  - Verification: `! git grep -nF -e "roadmap store factory is refused" -- docs`

## 5. Archive

- [x] 5.1 Archive the change
  - Verification: `uv run devops openspec archive 3746-roadmap-tests-install-store-hook`

## Workflow follow-up

- Four patch sites stay (two `uvicorn.run`, two `run_due_jobs`) and one case is dropped (`--force` with a cache hit). Each needs a seam that another item owns: see Feasibility in proposal.md.
- Part 3 of #1335 splits the four largest roadmap test files.
