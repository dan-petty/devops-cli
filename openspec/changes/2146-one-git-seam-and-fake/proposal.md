# Proposal

## Why

Issue #2146. Tests of `src/` start git more than they start any other program. The audit of 2026-10-24 found 705 tests that start git, with a median of 6 starts per test. A test that starts only git takes a median of 0.194 s. A test that starts nothing takes 0.026 s. The three test files of this issue (`tests/test_git_operations.py`, `tests/test_git_worktree.py` and `tests/test_core_repo.py`) start git 110 times in 29 tests.

devops-cli has no git fake, because git has two ways in. 27 modules start git through the process runner. Three users start it through GitPython, which calls `subprocess.Popen` inside its own code, so the process fake does not see those starts.

## What Changes

- The process runner (`ProcessRunner`, `run_subprocess`) is the one seam for git. The three GitPython users move to it: `git/operations.py` (`clone_repo`, `fetch_all`, `pull_tracking`, `create_branch`, `commit_snapshot`, `list_branches`, `delete_merged_branches`), `commands/repos.py` (`_current_branch`) and `ai/research/edges.py` (`extract_git_co_changes`). No module of `src/` imports GitPython any more, and GitPython leaves the dependencies. An invariant test fails when a module imports it or starts git by a way other than the runner.
- `commit_snapshot` runs `git add`, `git write-tree` and `git commit-tree`. It gives the same commit id as before for the same files: the pinned id `63b6e3c00959a24f7f5badfa9508a96cca4504ae` of the golden review set holds. Caller overrides of `GIT_AUTHOR_DATE` and `GIT_COMMITTER_DATE` pass the environment guard, like the four other git keys that run no program.
- `tests/support/fakes/git.py` holds `GitFake`, a process fake that answers each git command from a transcript, and the `git_fake` fixture installs it through the seam. A test with the fixture cannot start a real git: the hermetic floor refuses it. A git command with no transcript fails the test and names the command.
- A transcript is a file of `tests/fixtures/git/`. It holds the commands that one scenario started, with the arguments, the exit code, the standard output and the standard error of each, and the result the scenario gave. The scenarios are code in `tests/support/git_scenarios.py`. A transcript holds `{root}` in place of the directory the scenario ran in. It holds no host path, user name or e-mail address except `example.com`.
- `tests/test_git_contract.py` runs every transcript over the code of `src/` with the process fake, and over `GitFake`. It checks that both give the recorded result and that the code starts the recorded commands. It starts no program.
- A `devops ci` row, `git`, records every scenario again with the real git, outside pytest, and fails when a transcript differs. The row runs in the static job on the stock runner.
- The three test files use the fake and start no git. Four other test files that used GitPython or its patch points (`tests/test_ssh_host_keys.py`, `tests/test_ai_research_forage.py`, `tests/test_review_score.py`, `tests/test_repos.py`) move with the code they test.
- `docs/TESTING.md` describes the git seam, the fake and the contract suite. The GitPython manual leaves the knowledge base.
- The environment guard of `build_subprocess_env` accepts two more git keys, so the spec `subprocess-environment` changes: two requirements are modified.
- This change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `subprocess-environment`: a caller override of `GIT_AUTHOR_DATE` or `GIT_COMMITTER_DATE` reaches the child, as the five other accepted git keys do.

## Impact

- Code: `src/devops_cli/git/operations.py`, `src/devops_cli/commands/repos.py`, `src/devops_cli/ai/research/edges.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/commands/ci.py`, `src/devops_cli/lang/en/messages.py`, `pyproject.toml`, `uv.lock`.
- Tests: `tests/support/fakes/git.py`, `tests/support/git_scenarios.py`, `tests/support/git_recording.py`, `tests/test_git_contract.py` and `tests/fixtures/git/` (all new); `tests/conftest.py`, `tests/test_git_operations.py`, `tests/test_git_worktree.py`, `tests/test_core_repo.py`, `tests/test_architectural_invariants.py`, `tests/test_subprocess_env_boundary.py`, `tests/test_ci.py` and the four files above.
- Documents: `docs/TESTING.md`, the knowledge base, the generated command reference.

## Feasibility

- On `origin/main` 524db954, 27 modules start git with an argument list that begins with `git` or `CONST_GIT_CLI`. A scan of the syntax trees of `src/devops_cli` (call sites of each list) shows that every one of them calls `run_subprocess`, or a wrapper that calls it, or a runner that the caller gives (`k8s/argocd_overrides.py`). The seam exists. `rg -n "subprocess\.(run|Popen)"` over `src/devops_cli` lists seven direct starts, in `core/process.py`, `sandbox/host.py`, `commands/devcontainer.py` (the bootstrap script), `commands/k8s/networking.py` (kubectl), `ai/gateway_tune.py` (kubectl) and `ai/review/template_sweep.py` (the checkers). None starts git.
- GitPython 3.2.1 cannot sit behind the runner. `Git.execute` (`git/cmd.py`) builds its own `Popen` and, with `as_process=True`, returns the running child. `Git._get_persistent_cmd` keeps one `git cat-file --batch` child alive for the life of the `Repo`, and `Remote.fetch`, `Remote.pull` and `Repo.clone_from` read the progress of a running child. The runner runs a command to its end and returns its text, so it can serve none of these. GitPython users therefore move to the runner.
- The seven functions that used GitPython need nine git commands: `clone`, `remote`, `fetch --prune`, `pull`, `for-each-ref`, `branch --show-current`, `branch --merged`, `branch -d`, `checkout -b`, and for `commit_snapshot` `add`, `write-tree` and `commit-tree`. Run with git 2.55.0, in a scratch repository with `GIT_CONFIG_GLOBAL=/dev/null`, `git add --force`, `git write-tree` and `git commit-tree --no-gpg-sign` with `GIT_AUTHOR_DATE=2026-10-03T00:00:00+00:00` and an empty e-mail gave the commit `63b6e3c00959a24f7f5badfa9508a96cca4504ae`, the id that GitPython gave and that `tests/test_git_operations.py` pins. `git for-each-ref --format=%(upstream:remotename)` gave `origin` for a tracking branch and nothing for a branch with none. `git log --diff-merges=first-parent --no-renames --name-only -z` gave the files of each commit of a path, a merge included, in one process: `Commit.stats` started one `git diff --numstat` for each commit.
- The environment guard refuses `GIT_AUTHOR_DATE` today (`CONST_GIT_ACCEPTED_ENV` names five keys). The date is the one input of `commit-tree` that has no argument. Both date keys run no program and write no file (git(1)), so they join the accepted keys.
- `deptry src` fails on a dependency that no module imports, so GitPython leaves `pyproject.toml` and `uv.lock` in the same change. `rg -n "import git|from git "` shows that two tests (`tests/test_ai_research_forage.py` and `tests/test_review_score.py`) import it; both build or count commits, which the `git` fixture does.
- Time and starts of the three files before the change, on 2026-10-30 at 524db954: 29 tests, 110 git starts counted by a `git` wrapper first on `PATH`, 2.62 s for pytest.

## Existing Tool Considered

- `pytest-subprocess` fakes `subprocess.Popen` and would see the GitPython starts. It has no transcript file, no recorder and no check against the real git. It patches a stdlib object that `ProcessFake` already stands in for, and docs/TESTING.md allows that patch for stdlib edges only. Rejected.
- `vcrpy` and `betamax` record HTTP, not child processes. Rejected.
- `dulwich` is a maintained pure-Python git. It has no command-line surface: the code of `src/` starts the `git` program with arguments, so a fake of the program has to answer arguments. Rejected as the fake. Not needed for the code either, because 27 modules already use the git program.
- GitPython is the library the code used. It cannot sit behind the runner (see Feasibility). The three users move to the git program through the runner, as the 27 other modules do.
- The fake builds on `ProcessFake`, and the recorder and scenarios follow `tests/support/openspec_recording.py` and `tests/support/fakes/openspec.py`, which solve the same problem for OpenSpec.
- Cost of building instead (rule 3): about 900k tokens to build in one session, about 6 hours elapsed. Upkeep is one command that re-records the scenarios, about 5 s with git installed, and the CI row runs it each time. A defect that the row finds is a changed transcript to review.
- The change deletes GitPython from the dependencies, its knowledge-base manual, seven GitPython-backed bodies of `git/operations.py`, and the 14 `MagicMock` repositories and `gitlib` patches of `tests/test_git_operations.py` and `tests/test_ssh_host_keys.py`.
