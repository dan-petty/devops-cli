# Task: The Second-sgconfig Check Counts the Files Git Tracks (#1787)

**Issue**: [#1787](https://github.com/dan-petty/devops-cli/issues/1787)
**Scope**: scope/ci
**Feasibility**: I read `_sgconfig_escapes`, `_network_construct_escapes` and each other filesystem walk of `tests/test_architectural_invariants.py` at `release/v0.2.39`. I reproduced the failure of the issue with a real nested worktree under `.claude/worktrees` of my own worktree. I ran `git ls-files` with the pathspec in a test repository and in the worktree. I measured, for each walk, the files it reads that git does not track. The production code has no defect, so the change touches no file in `src/`. The section "Evidence" gives the details.

## Description

`_sgconfig_escapes` reported "a second sgconfig.yml" for each `sgconfig.yml` that `project.rglob` found. It read the working tree, not the committed files. A nested worktree under `.claude/worktrees/` is a full checkout with its own `sgconfig.yml`, so it failed the check. Scratch under `.data/` failed it in the same way. Git ignores both, and the check passed on CI.

- **The listing.** `_tracked_paths(project, *pathspecs)` runs `git ls-files -z` in the project and returns the names. `_sgconfig_escapes` asks for `:(glob)**/sgconfig.yml` and excludes the root file with `:(exclude)sgconfig.yml`. Git does the matching, so the check holds no ignore logic of its own.
- **The excluded directory.** The old check skipped each path with a part named `repos`. That part could match a directory above the project, and it hid a real second file under any `repos` directory. The tracked listing makes the exclusion unnecessary, so it is gone.
- **No repository, no pass.** `_git_output` ends the test with `git ls-files failed in <project>` and the message of git when a git command fails. A project that is not a git repository fails the check. The check cannot pass on an empty listing. The test sets `GIT_CEILING_DIRECTORIES` to the parent of `tmp_path` and matches the message of `_git_output`, so a temporary directory inside a repository, or a git in another language, does not change the result.
- **The helper that was not reused.** `get_git_tracked_files` in `tests/support/workspace_tripwire.py` catches each exception and returns an empty list. A project that is not a repository would then pass the check.
- **The source files.** `_network_construct_escapes` read `src` with `rglob("*")`, and the issue names it. It now reads the tracked files under `src`. A source file that `.gitignore` matches but no commit holds no longer fails the check. A tracked source that `.gitignore` matches is still reported, because Ruff skips it.
- **The older listing.** `_unscanned_tracked_sources` keeps its own `git ls-files` call. It fails loud on a git failure, so the change leaves it alone and keeps the diff small beside the code of the suppression ceiling.
- **The environment of a hook.** A commit hook in a linked worktree sets `GIT_DIR` and `GIT_INDEX_FILE` to the real worktree. A test that starts git in `tmp_path` then writes to the real index. The fixture `git_environment` removes the variables that `git rev-parse --local-env-vars` names. The fixture `git_project` builds on it. The test `test_a_git_project_leaves_the_repository_of_a_commit_hook_alone` sets both variables to an empty directory and checks that the directory stays empty.
- **One older test.** `test_a_tracked_stub_or_notebook_under_a_scanned_root_is_named` starts git in `tmp_path` and now uses `git_project`. My own commit hook runs this file, so the test would have written `src/api.pyi` and `tests/analysis.ipynb` into the index of the commit.

## Evidence

- **The failure of the issue.** I made a nested worktree under `.claude/worktrees/` of my worktree, with `sgconfig.yml` under `.data/agent/scratch/astgrep/` beside it. The base test file failed: `assert ['.claude/wor...sgconfig.yml'] == []`, with `.claude/worktrees/throwaway-1787/sgconfig.yml: a second sgconfig.yml` first. The fixed test file passed: 88 passed.
- **The new tests on the old logic.** Four of the five new tests failed for the reason of the issue. The fifth, the hook test, guards the fixture and has its own mutation proof below. The untracked-sgconfig test listed the nested and the scratch file. The tracked-beside-untracked test listed `.data/sgconfig.yml`. The ignored-source test listed `src/target/scratch.py: matched by .gitignore`. The no-repository test failed with `DID NOT RAISE`.
- **Mutation proofs.** I staged the work and changed one line at a time. I restored the file with `git checkout -- tests/test_architectural_invariants.py` after each run.
  - `rglob` back in `_sgconfig_escapes`: the untracked-sgconfig test and the tracked-beside-untracked test failed.
  - The tracked listing replaced by `[]`: the parameter `second-sgconfig` and the tracked-beside-untracked test failed.
  - `rglob` back in `covered`: the ignored-source test failed.
  - `covered = []`: the parameter `ignore-file-hides-source` failed.
  - `_git_output` that never fails: the no-repository test failed.
  - The pathspec `:(glob)*/sgconfig.yml`, which reaches one directory level, in place of `:(glob)**/sgconfig.yml`: the parameter `second-sgconfig` and the tracked-beside-untracked test failed. Both tests hold a file at `subdir/deeper/sgconfig.yml` for this reason.
  - `git_environment` that removes no variable: the hook test failed.
  - The no-repository test with no `GIT_CEILING_DIRECTORIES`, run with `--basetemp` inside a repository: it failed with `DID NOT RAISE`. With the ceiling, it passed in both places.
- **The hook variables.** I ran the tests with `GIT_DIR` and `GIT_INDEX_FILE` set to a decoy repository in `.data/agent/scratch/`. With `git_environment`, the decoy index held 0 entries. With the removal turned off, the decoy index held 33 entries. A raw hook in a linked worktree, in a throwaway repository, showed the same: `git add` in a temporary directory put its file into the commit.
- **The other walks.** I ran each walk of the test module and of `tests/support/trees.py` in my worktree, with the nested worktree and the scratch file present. I counted the files the walk reads that `git ls-files` does not list.
  - `project.rglob("sgconfig.yml")` read 2 untracked files: the nested and the scratch file.
  - `src.rglob("*")` read untracked files, all under `__pycache__`, and no suffix filter of the check admits them.
  - Every other walk read 0 untracked files outside `__pycache__`.

## Existing tools considered

- **git.** `git ls-files` names the tracked files, and its pathspecs select by name. The change adopts it. It adds no ignore logic, no list of directory names and no new dependency.
- **`pathspec`.** The project depends on it, but the check does not need it. It would only read the ignore rules, and the tracked listing makes them unnecessary.
- **The helper `_tracked_paths`.** It has 4 lines. I estimate that it cost about 25,000 tokens and 40 minutes to write and check, with the tests. It needs no upkeep.

## Acceptance Criteria

- [x] An untracked `sgconfig.yml` under `.data/`, and one in a nested worktree under `.claude/worktrees/`, do not fail the check.
- [x] A tracked second `sgconfig.yml` still fails the check at any depth and the message names it.
- [x] A project that is not a git repository fails the check, also when its temporary directory lies inside another repository.
- [x] Git in a temporary repository does not write to the repository variables that a commit hook sets.
- [x] An untracked source file that `.gitignore` matches does not fail the check, and a tracked one still does.
- [x] The invariants file passes in a worktree that holds a nested worktree, and the base fails there.
- [x] Each new test fails when I undo the line it guards.
- [x] `uv run devops ci test tests/test_architectural_invariants.py` passes.
- Pending a person: run `uv run devops ci` in the primary checkout, which holds nested worktrees, and see `test_the_network_construct_gate_has_no_escape` pass.

## Deliverables

- [x] `tests/test_architectural_invariants.py`: `_git_output`, `_tracked_paths`, the tracked listing in `_sgconfig_escapes` and `_network_construct_escapes`, the fixtures `git_environment`, `git_project` and `hook_git_variables`, and the new tests.
- [x] `docs/agent/tasks/task-1787-the-second-sgconfig-check-counts-tracked-files.md`.
- [x] `changelog.d/1787.md`.

## Not Done

- Not done: `test_finding_is_constructed_only_by_admission` reads `src/devops_cli` (does not read a root that can hold nested worktrees).
- Not done: `_helper_modules`, `_support_packages` and `_support_package_imports` read `tests` and `tests/support` (do not read a root that can hold nested worktrees).
- Not done: `_blind_exception_assertions` reads `tests` (does not read a root that can hold nested worktrees).
- Not done: `test_no_direct_data_dir_path_construction_in_src` and `_no_mutate_pragmas` read `src` (do not read a root that can hold nested worktrees).
- Not done: `_collect_suppressions` reads `src` and `tests` (does not read a root that can hold nested worktrees).
- Not done: the facade test reads `src/devops_cli/ai/knowledge_base`, and `_find_package_submodules` lists one package directory (do not read a root that can hold nested worktrees).
- Not done: the two workflow tests read `.github/workflows` (do not read a root that can hold nested worktrees).
- Not done: `_stray_root_scripts` lists the files in the project root. A nested worktree is a directory, so the check skips it. The check exists to find scripts that no commit holds, so a tracked listing would defeat it.
- Not done: `parse_source_trees` and `parse_test_trees` in `tests/support/trees.py` read `src` and `tests` (do not read a root that can hold nested worktrees).
- Pending a person: file an issue for the other test modules that start git in `tmp_path` with no removal of `GIT_DIR` and `GIT_INDEX_FILE`, for example `tests/test_ci_cache.py` and `tests/test_gitignore_evaluation.py`. A commit hook in a linked worktree can write their files into the commit. One removal in the hermetic floor of the root conftest would cover them all. I did not run those tests with the hook variables set.
