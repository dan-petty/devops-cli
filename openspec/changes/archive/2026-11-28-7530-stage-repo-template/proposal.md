# Proposal: #7530

## Why

The `stage_repo` fixture builds its repository with real git in the setup of each test: 11 git processes (`init --bare`, `clone`, three `config` calls, `switch`, `add`, `commit`, `push`, `symbolic-ref`, `remote set-head`). On main CI run 46103047841, the 1,579 tests that use it took 1,151.6 s of the 3,641 s of test time, a mean of 0.73 s for each test (#7530). The tests that use `git_fake` have a mean of 0.11 s.

docs/TESTING.md names #2174 and #2178 to #2183 as the remaining move of tests to `git_fake`. All seven issues are closed as completed, so the "Not yet" list does not name the real remaining work.

## What Changes

- The session fixture `stage_repo_template` (`tests/support/roadmap_stage.py`) builds the repository of `stage_repo` once in each test process, in a folder from `tmp_path_factory`.
- `stage_repo` copies the template into `tmp_path` with `shutil.copytree`. It sets the URL of the clone's `origin` to the copy of `origin` and refreshes the index of the clone, which starts 2 git processes. The tests keep their assertions.
- docs/TESTING.md: the "Not yet" list names the move of the tests that start real git to `git_fake` (#7533), and "Run time" says that `stage_repo` copies a template.
- The change alters only tests and a document. No command, option, message, manifest or Service behavior changes, so the change has no spec delta and sets `skip_specs: true`.

## Capabilities

None. The change has no spec delta.

## Impact

- The setup of each of the 1,579 tests starts 2 git processes in place of 11.
- A local run of the 117 modules on 4 pinned CPUs (`taskset -c 0-3`, `pytest -n 4 --durations=0`, one run on each tree) took 200.1 s in the setup of the 1,579 tests before the change and 143.3 s after it. The CPU time of the run went from 1,124.6 s to 1,063.1 s.
- `staged_repo`, `job_world` and `planned_world` keep their own git setup, and the jobs under test keep `git_for_real`. #7533 moves them to `git_fake`.
- The change fits one pull request.

## Feasibility

- The set: the inventory of the suite at 14d401ac3 (`pytest --collect-only` with a plugin that writes the fixture closure of each test) gives 1,579 tests in 117 modules whose closure holds `stage_repo`. Main CI run 46103047841 at e4f764163 ran all 1,579 of them.
- The copy: a script outside pytest on git 2.55.0 and Python 3.14.10, 40 repetitions on 4 pinned CPUs, measured the build at 70.7 ms of CPU, `shutil.copytree` with `git remote set-url` and `git update-index -q --refresh` at 21.1 ms, and `git clone --local --no-hardlinks` of both repositories at 44.4 ms.
- The isolation: a copy holds no hard link and no path of the template except the URL of `origin`, which the fixture sets again. Each test changes only its own copy, and no fixture or test but `stage_repo` reads `stage_repo_template`. HOME, and with it the git config of the hermetic floor, is the same for the whole test process (`isolate_home` in `tests/support/bootstrap.py`), so the template and a build in a test start git with the same config.

## Existing Tool Considered

`shutil.copytree` of the standard library copies the repositories, and `git remote set-url` and `git update-index --refresh` make the copy equal to a new build. `git clone --local --no-hardlinks` was measured too, and is slower (design.md). The change writes no copy logic of its own and deletes no internal code: the build of the repository moves from `stage_repo` into `_build_stage_repo`.
