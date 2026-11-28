# Design

## Decisions

- **Build the repository once in each test process.** `stage_repo_template` is a session fixture. Under xdist each worker is its own session, so each worker builds the template once, in a folder from `tmp_path_factory` under the run's temporary directory, which the host path guard allows.
- **Copy with `shutil.copytree`, then 2 git processes.** The clone's `.git/config` holds the absolute path of the template's `origin`, so `git remote set-url origin <copy>` points it at the copy. A copy has other inode and ctime values than the stat data in the index, so `git update-index -q --refresh` records the stat data of the copied files. The copy is then equal to a new build for each git command.
- **Keep the layers on top of `stage_repo`.** `staged_repo`, `job_world` and `planned_world` push their branch and commits on the copy as before, so a test that asks for `stage_repo` and `staged_repo` gets one repository.

## Rejected alternatives

- **`git clone --local --no-hardlinks` of the template.** It needs two clones (the bare `origin` and the clone) and the three `config` calls again. It took 44.4 ms of CPU for each copy, against 21.1 ms for `shutil.copytree` with the 2 git processes (scratch measurement, 40 repetitions, git 2.55.0).
- **A copy with no refresh of the index.** On a copy with no refresh, `git diff-index --quiet HEAD` exits 1 with no change to a file, because the index holds the stat data of the template. The porcelain commands refresh the index first (`git diff --quiet`, `git switch` and `git rebase` exit 0 on such a copy), and no module under `src/` starts `diff-index`, `diff-files` or `update-index`. The refresh costs 2.1 ms of CPU for each copy and keeps the copy equal to a new build for the plumbing commands too.
- **A template for `staged_repo`, `job_world` and `planned_world` too.** Their git state comes from function-scoped fixtures that test modules override or parametrize (`staged_tasks`, `staged_files`, `plan_subject`, `planned_tasks`), so a template needs a key for each set of values. And `staged_repo` changes the repository of `stage_repo`, so a test that asks for both gets one repository. A template of the layer has to keep both properties. The move to `git_fake` (#7533) removes this setup.
- **Move the tests to `git_fake` now.** The jobs under test run git for real through `git_for_real`, so a transcript must hold every git call of each job. That is the work of #7533 and does not fit this pull request.
