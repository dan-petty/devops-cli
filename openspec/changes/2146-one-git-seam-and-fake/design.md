# Design

## Decisions

### The seam is the process runner, and GitPython leaves

`run_subprocess` and `get_process_runner` are the seam of git, as they are the seam of every other program. 27 modules use it already. The three GitPython users move to it, so the 28th and later modules need no change and the fake sees every start of git.

`git/operations.py` keeps its public functions and their errors. Each function runs plain git commands and reads their text:

- `clone_repo`: `git clone -- <url> <dest>`.
- `fetch_all`: `git remote`, then `git fetch --prune <remote>` for each remote.
- `pull_tracking`: `git branch --show-current`, `git config --get branch.<branch>.remote`, `git remote`, then `git pull <remote> <branch>`. `for-each-ref --format=%(upstream:remotename)` is not used: it gives nothing for a branch whose remote does not exist, where the setting names it.
- `create_branch`: `git show-ref --verify --quiet refs/heads/<name>`, then `git checkout -b <name>`.
- `list_branches` and `delete_merged_branches`: `git branch --show-current`, `git for-each-ref --format=%(refname) refs/heads refs/remotes`, `git branch --merged <default>` and `git branch -d`.
- `commit_snapshot`: `git init`, `git add --force`, `git write-tree` and `git commit-tree --no-gpg-sign` with the message on standard input and the author and date in the environment. The ref is set by `git update-ref`.
- `current_branch` is new and shared by `list_branches` and `commands/repos.py`. `extract_git_co_changes` runs `git rev-list` for the commits of a path and one `git log --no-walk --stdin` for the files of all of them, where GitPython started one `git diff` for each commit.

Read commands pass `local_read=True`, so a dry run still reads. A command that changes the repository or reaches a remote is a planned request in a dry run, as every other mutating start of the runner.

### The fake is a process fake with transcripts

`GitFake` subclasses `ProcessFake`, so it records `ProcessCall` and keeps the dry-run and timeout rules of the process fake. It answers a command whose first word is `git` from the exchanges of the scenarios the test loaded. A command with no exchange fails the test and names the command. Any other program gets the `ProcessFake` answer.

An exchange is found by its arguments, with the directory of the test written as `{root}`. When a scenario records one set of arguments more than once, the fake answers the first call with the first exchange, the second call with the second, and the last answer again after that. This holds the cases where the answer changes between two calls (`git diff HEAD` before and after an edit).

The environment of a call is not part of the key. A test that cares reads it from `fake.calls`.

### A transcript is the record of one scenario

A scenario is a function of `tests/support/git_scenarios.py`. It builds a repository with `ws.git(...)` and `ws.write(...)`, then calls the code of `src/` and returns a value that JSON can hold. When the scenario is recorded, `ws.git` runs the real git without a record, and the process runner records every command the code starts. When it is replayed, `ws.git` does nothing, `ws.write` still writes files, and the commands go to a fake. One function gives both runs, so a scenario cannot drift from its record.

The record sets the identity, the dates, `HOME` and the configuration files, so the commit ids and the text do not depend on the host. It writes `{root}` for the scratch directory, and fails when the text still holds a host path, a user name or an e-mail address that is not `example.com`.

### The contract suite checks the fake against the code and the record against git

`tests/test_git_contract.py` runs each scenario twice: over a `ProcessFake` that answers the recorded exchanges in order, and over `GitFake`. Both runs must give the recorded result, and the first must start exactly the recorded commands in order. The `devops ci` row `git` records each scenario with the real git again and fails when the transcript differs. Together they fix the fake to the code and the transcript to git.

### The fixture refuses real git

`git_fake` puts a guard on `subprocess.Popen` for the length of the test. A test with the fixture that reaches a real git, through the `git` fixture or a direct `subprocess` call, fails. This holds the criterion "start no git" for the three files and for every file that migrates later. The floor of `tests/conftest.py` still allows git in the other tests, until the last of the follow-up issues moves them.

### The row runs in the static job

The row is in `get_check_specs`, so `devops ci --check --skip test,outdated,actionlint` runs it in the Static Analysis job of the stock runner, in parallel with the other rows. It takes about 5 s.

## Rejected alternatives

- **GitPython behind the runner**: `Git.execute` builds its own `Popen`, returns the running child for `as_process=True`, and `_get_persistent_cmd` keeps a `git cat-file --batch` child open. The runner runs a command to its end. See Feasibility.
- **A fake with no transcripts, written by hand**: the answers would be what the author thinks git prints. The row that records git again is what tells a changed answer.
- **`pytest-subprocess`**: see Existing Tool Considered.
- **One transcript file per command**: a command's answer depends on the repository it ran in, so a file per command cannot hold the cases (a rename, a link, a refused fetch). A file per scenario holds the repository state in its name.
- **Keep the test files on real git and add the fake beside them**: criterion 6 asks that the three files start no git, and the audit counts the real starts as the cost.
