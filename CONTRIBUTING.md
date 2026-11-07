# Contributing to DevOps CLI

Thank you for your interest in contributing to DevOps CLI! This document outlines our engineering standards, development workflow, and pull request governance.

---

## 1. Development Philosophy & Core Invariants

These rules apply to every contributor. [`AGENTS.md`](AGENTS.md) sends agents here.

- **Test-First Implementation (TDD)**: New behavior **must** have a failing test written first. Tests serve as the executable documentation of public interfaces, edge cases, and architectural boundaries. Every other change (a document, a manifest, a workflow, a deletion or a refactor that keeps behavior, an edit of tests only, or data) gets no test. It names a command that proves it. See [`docs/TESTING.md`](docs/TESTING.md), section "Which change gets a test".
- **Complexity and Nesting Caps**:
  - Ruff caps cyclomatic complexity at 10 (`C901`) in `pyproject.toml`. `uv run devops ci` and the pre-commit `ruff-check` hook run it with `--config pyproject.toml`, and the `lint` row checks the resolved settings of Ruff and the walk of Ruff against the files that git tracks (`tests/gate/ruff_config.py`), while `tests/commands/test_ruff_complexity_cap.py` checks every `ruff check` command. Functions over the cap when it was turned on carry `# noqa: C901`, and `tests/test_architectural_invariants.py` keeps their count from growing. `devops scan complexity` reports the same McCabe count and does not gate.
  - Ruff caps nesting at 4 nested blocks in a function (`PLR1702`, `max-nested-blocks = 4` in `pyproject.toml`). It counts `if`, `for`, `while`, `with` and `try` blocks, and not `match` blocks. `PLR1702` is a preview rule, so `pyproject.toml` turns on lint preview with `explicit-preview-rules`, and the `lint` row checks the cap, the preview settings and the formatter's stable style (`tests/gate/ruff_config.py`).
  - Decompose multi-step procedures into dedicated single-responsibility helpers and pure predicates.
  - For a closed set of cases, use `match` with `assert_never`, or a table. Do not write an `if`/`elif` chain.
- **Closed Lists and Standard Parsers**:
  - Match a value against a list of strings only when the list covers a closed domain, such as one that an RFC or a language grammar defines.
  - For an open domain, use a parser (`ast`, `tokenize`, `urllib.parse`, `ipaddress`, `packaging`) or an official registry, such as the Public Suffix List through `tldextract`.
  - Declare each list, tuple or frozen set that matches, classifies or filters values as a named module-level table beside its one owner: the module that reads it, or the `constants.py` of its package when several modules of one package read it. Move the table to `src/devops_cli/config/constants.py` or `src/devops_cli/config/defaults.py` only when a module of a second package imports it. When you change the owner of a table in `config/` that only one package reads, move the table to its owner in the same pull request.
- **Names**: Name each file, module, class and function for its responsibility. Do not use a placeholder name, such as `temp_util.py`. Ruff `N` checks the form.
- **Line Breaks Belong to Source Files**: Hard-wrap text only in source files and Markdown documents. Write emitted text (terminal messages, Rich renderables, log records, `lang/en/` strings) as continuous paragraphs. Split a long string in the source with implicit string concatenation.
- **Strongly Typed Domain Exceptions**:
  - All domain error states must raise strongly typed exceptions inheriting from `DevOpsCLIError` under `src/devops_cli/exceptions/`.
  - Each exception class declares its `error_code` and its `exit_code` as class attributes, and declares only the one that differs from its base. Its `__init__` adds detail keys or builds the message, or it has no `__init__`. Pass `exit_code=` only to give one error a status that its class does not have, such as the exit status of a failed subprocess.
  - Raising bare Python built-in exceptions (`ValueError`, `RuntimeError`, `TypeError`) is strictly prohibited.
  - A command raises the error and does not report it. The wrapper of `new_typer()` reports each `DevOpsCLIError` that a command or a callback raises, and exits with the error's `exit_code` ([ARCHITECTURE.md](ARCHITECTURE.md), section 7). Catch a `DevOpsCLIError` in a command only to recover from it.
- **Minimum 85% Code Coverage, and 90% of the Changed Lines**: Continuous quality gate. `devops ci` enforces 85% of the lines and branches of `src/` (`fail_under` in `pyproject.toml`). The aggregate CI job keeps `.data/coverage.xml` as an artifact for 7 days. A pull request must also cover 90% of its changed lines: the `Changed-Line Coverage` step of CI fails below that.
- **Pre-1.0 Alpha Status & Zero Backwards Compatibility**: DevOps CLI is pre-1.0 alpha software. Until at least release `1.0.0`, there is no intention of maintaining backwards compatibility. The codebase must remain clean of legacy references and obsolete shims at all times so that it can reach maturity at a reasonable rate. Any version after `1.0.0` will follow strict semantic versioning conventions, and employ all change management best practices including feature flags, deprecations, and migration functionality.
- **Zero Zombie Code & Legacy Remnants**: Ruthlessly remove obsolete shims, legacy workarounds, and deprecated aliases. Never introduce compatibility shims during the pre-1.0 development cycle.

---

## 2. Local Environment Setup

We use modern Python 3.14+ runtime tooling powered by [`uv`](https://github.com/astral-sh/uv).

```bash
# 1. Clone repository
git clone https://github.com/dan-petty/devops-cli.git
cd devops-cli

# 2. Synchronize virtual environment and all dependency groups
uv sync --all-groups --all-extras

# 3. Install pre-commit hooks
uv run pre-commit install
```

The container has a limit of 8192 processes and threads (`--pids-limit=8192` in `runArgs` of `.devcontainer/devcontainer.json`). Rootless Podman sets 2048 when the option is absent, and a burst of VS Code file searches filled that limit: the tools of agent sessions then failed with exit code 1 or `can't start new thread` (#3722). The extension `ms-python.vscode-python-envs` starts one `rg` search, with one thread for each CPU, for each file that a new worktree or virtual environment creates. A new limit takes effect only after a person rebuilds the container (`Dev Containers: Rebuild Container`). A restart or a reload does not apply it. `cat /sys/fs/cgroup/pids.max` shows the limit that applies.

---

## 3. Test-First Development Cycle (Inner Loop)

1. **Write Specification via Tests**:
   For new behavior, write the failing test first, as [`docs/TESTING.md`](docs/TESTING.md) describes, and run the file you changed. For any other change, run the command that proves it (for example `uv run devops ci docs`):
   ```bash
   uv run devops ci test <test-file>
   ```
   To start a new command or a new test file in project form, run `uv run devops new command <group> <command>` or `uv run devops new test <module>`. The skill [`new-scaffold`](.claude/skills/new-scaffold/SKILL.md) ([agents copy](.agents/skills/new-scaffold/SKILL.md)) gives the steps.
2. **Implement Feature Code**:
   Write concise, well-factored code in `src/devops_cli/` to satisfy the tests.
3. **Verify Fast Local Loop**:
   ```bash
   uv run ruff check path/to/modified.py
   uv run mypy path/to/modified.py
   uv run devops ci test tests/test_architectural_invariants.py
   ```
4. **Push Through the Fast Checks, and Merge Through CI**:
   The pre-push hooks run only the fast static checks: `uv run devops ci --check --only lint,format`, and `uv run devops ci --check --only actionlint,zizmor` when the push changes a file of `.github/workflows/` or `.github/actions/`. A push goes only when they pass. Never use `--no-verify`. The required checks of CI, `Static Analysis`, `Tests & Coverage` and `Semantic PR title`, must pass on the pull request before it merges (#1752). The release pull request runs the same checks on each new `main`, so its status shows a defect that two pull requests make together. To run every check before a push, run the full gate by hand:
   ```bash
   uv run devops ci
   ```
   Validates every check `devops ci` runs concurrently: Python runtime, tests, the coverage floor, linting, formatting, strict typing, dependency audit, security scanning, the wheel and sdist build, workflow actionlint and zizmor, and documentation freshness.

   Several agents share one host, and the full test suite starts one pytest worker for each CPU, so gates that run at once make each other several times slower (11189 tests took 247 s alone and 440 s each beside a second gate). A run that selects `test`, `security` or `typecheck`, and the full-suite `devops ci test` and `devops ci coverage`, therefore wait for a free gate slot first and say which process and worktree hold the slots. One slot exists for each 16 CPUs, and at least one; `ci.gate_slots` (or `DEVOPS_CLI_CI_GATE_SLOTS`) sets the number. The pre-push hook, a test run narrowed by paths or by `-n`, a dry run and a cached verdict never wait. The operating system frees a slot when its holder ends, also when it is killed. The wait is not part of the gate time and is recorded as the histogram `devops_cli_ci_gate_slot_wait_seconds`.

### Shell notes for agents

In the devcontainer, the Bash tool of Claude Code runs zsh. `SHELL` is `/bin/zsh`, because the `common-utils` feature in `.devcontainer/devcontainer.json` makes zsh the default shell of the user `vscode`. The tool of another agent, or a machine outside the devcontainer, can run bash. Run `echo $ZSH_VERSION` to check: it prints a version only in zsh.

In bash, `${=F}`, `${(f)...}` and `print -r --` fail. The forms `printf '%s'`, `$(cmd)` and `"${files[@]}"` work in both shells. Three behaviors cause wrong commands.

1. **zsh does not split an unquoted variable at white space.** A variable that holds a file list is one argument with newlines, and `ruff` reports `io-error`. Split the list with `${=F}`, with an array, or with a `$(cmd)` in the argument list. The git command lists Python files that exist. `ruff` lints a file of another type as Python, and it reports an error for a deleted file:

   ```zsh
   F=$(git diff --name-only --diff-filter=d origin/main...HEAD -- '*.py')
   # wrong: one argument with newlines
   uv run ruff check $F
   # right, but it splits a name with a space
   uv run ruff check ${=F}
   # right, but it splits a name with a space
   uv run ruff check $(git diff --name-only --diff-filter=d origin/main...HEAD -- '*.py')
   # right: it splits at newlines and keeps a name with a space
   files=(${(f)"$(git diff --name-only --diff-filter=d origin/main...HEAD -- '*.py')"})
   uv run ruff check "${files[@]}"
   ```

   Git quotes a non-ASCII name. For such a name, use `git diff -z` and split with `${(0)...}`.

2. **A word that starts with `=` and has more text is a command lookup.** `echo =========` prints `======== not found`, and the shell runs nothing else in that command. Print a separator with `printf`:

   ```zsh
   echo =========           # wrong
   printf '%s\n' '-----'    # right
   ```

3. **JSON from `uv run devops gh api` breaks in two ways.** The command writes a `Bytecode compiled` line and an `Elapsed:` line to stderr. In a git worktree, `uv run` also writes a `warning: VIRTUAL_ENV` line. The Bash tool shows these lines around the reply, and a `2>&1` pipe mixes them into the JSON.

   In zsh, `echo "$VAR"` expands backslash escapes. A `\n` in a JSON string then becomes a raw newline, and the parser fails. Pipe stdout directly. Print a variable with `print -r --` or `printf '%s'`. Or read one field with `--jq`:

   ```zsh
   P=$(uv run devops gh api repos/dan-petty/devops-cli/pulls/<n>)
   echo "$P" | python3 -m json.tool >/dev/null                                              # wrong: echo expands \n
   uv run devops gh api repos/dan-petty/devops-cli/pulls/<n> 2>&1 | python3 -m json.tool    # wrong: stderr lines in the JSON
   print -r -- "$P" | python3 -m json.tool >/dev/null                                       # right, zsh only
   printf '%s' "$P" | python3 -m json.tool >/dev/null                                       # right, zsh and bash
   uv run devops gh api repos/dan-petty/devops-cli/pulls/<n> | python3 -m json.tool         # right: a direct pipe carries stdout only
   uv run devops gh api repos/dan-petty/devops-cli/pulls/<n> --jq .title                    # right: one field
   ```

---

## 4. Git Hygiene & Branch Management

- **Branch Naming**: [Section 5](#5-naming) gives the form of a branch name. The `no-commit-to-branch` pre-commit hook refuses a commit on a branch that breaks it.
- **Branch Targeting**: Every topic branch targets `main`. A maintainer squash-merges the pull request.
- **Drafts First**:
  - Open every pull request with `devops pr create`. It always opens a draft.
  - `devops pr create` adds the labels that the title gives, with the rule of intake: `fix(ai): ...` gets `type/bug` and `scope/ai`. Do not add these labels by hand. When a label cannot be added, the command names the pull request and the labels, and exits 1. The pull request stays open.
  - When all checks pass, mark the pull request ready with `devops pr ready <pr-number>`. This is the only way out of the draft.
  - `devops pr create` checks the title and the body before it opens anything, with the rules below, and exits 1 with every problem when one fails. `devops pr describe <issue> --summary "<summary>"` builds a title and a body that pass the check: the type and the scope come from the issue, the "why" from the proposal of the change folder, and it cuts no text. The module `src/devops_cli/roadmap/pull_form.py` holds the rules.
- **The Title Is the Changelog Line**:
  The pull request title is a Conventional Commit, and the `Semantic PR title` check enforces it. The squash commit takes the title as its subject, and GitHub adds ` (#<number>)` to it. release-please writes the changelog from these titles, so write the title for a reader of the changelog. The scope is one of the `scope/*` labels of `.github/labels.yml`, or `main` for the release pull request, and the `Semantic PR title` check and `devops pr create` refuse another scope. To use a new scope, declare its label in `.github/labels.yml` and add the scope to the `scopes` list of `.github/workflows/pr-title.yml` in the same pull request. The summary, the text after `<type>(<scope>): `, has at most 60 characters (an emoji counts as two, as the check counts UTF-16 units), and both checks refuse a longer one, and a summary that ends with `...` or is a placeholder such as `x`. The summary states the effect of the change. Put the evidence and the steps in the body or in the change folder:
  ```
  feat(k8s): add automated minikube helm adoption check
  fix(ai): prevent thread pool executor blocking on tool timeout
  docs(sdlc): add enterprise lifecycle manual
  ```
  Before `1.0.0` nothing is a breaking change, so a title has no `!` and a body has no `BREAKING CHANGE:` footer. Only these types add a line to the changelog:

  | Title type | Changelog section |
  | :--- | :--- |
  | `feat` | Features |
  | `fix` | Bug Fixes |
  | `perf` | Performance Improvements |
  | `refactor` | Code Refactoring |
  | `revert` | Reverts |

  The other types (`docs`, `test`, `build`, `ci`, `style`, `chore`) add no line. Do not edit `CHANGELOG.md`: release-please writes it in its release pull request. [`RELEASE_CYCLE.md`](RELEASE_CYCLE.md) tells what happens after the merge.
- **The Body Is the Commit Message**: The squash commit takes the pull request body as its message, so `git log` keeps the body after the merge. Write the body as it will read there: what the change does, and why, in at most 1,000 characters before the trailers. Do not repeat what the archived change folder holds, such as measurements, rejected alternatives and lists of files: the `Change:` line links to it. `devops pr create` refuses a longer body, a body with a placeholder for the text, and a body that holds text of the template. `devops pr check-readiness` names each problem of this form as a blocker and exits 1, where the base keeps `openspec/changes/`. End it with `Closes #<issue>` and the `Change:` line of the [template](.github/pull_request_template.md). A plan pull request (title `docs(openspec): plan #<issue> <summary>`) closes no issue: it has the line `Plans #<issue>` in place of `Closes`, then the `Change:` line of the active folder. The attribution lines of an agent come after the `Change:` line, never before `Closes`. Put test results, check status, steps for a person and the history of the issue in a comment on the pull request or on the issue, not in the body. When a push changes what the pull request does, change the body too.
- **Commits on the Branch**: Commits on a topic branch also follow the Conventional Commits format. The squash merge replaces them with one commit, with the title as its subject and the body as its message. So no hook checks the message of a commit on a branch.
- **Check Results Comment**: `devops pr evidence <number>` writes the check results of the head commit as one comment on the pull request: the head commit, a table of the checks with their conclusion and link, the link of the passing `Fail-to-Pass Check` run when the title is a fix, and a line for each skipped check. Every number comes from the check runs that GitHub returns, and the command takes no text of its own. It keeps one comment, which opens with a marker line and which its own login wrote. A new head commit updates that comment, and the command never posts a second one. It posts nothing when it cannot read the checks. `--attribution` adds a paragraph at the end of the comment for an agent. `--dry-run` prints the requests.
- **Fail-to-Pass Evidence**: A fix pull request cites its `fail-to-pass` check run in a comment (`devops ci fail-to-pass --base <ref>`, `.github/workflows/fail-to-pass.yml`). Do not type failure counts by hand. The check runs only for a pull request whose title is a fix (`fix(<scope>):` or `fix:`) and that changes `src/` outside `src/devops_cli/ai/knowledge_base/`. A fix that changes only tests, documents or dependencies gets no check. The check passes when three things hold. At least one changed test fails on the base. No failure carries the message of the host path guard of the test harness (`host path reached without a fake`). Every test that fails on the base is one that the fix adds or changes. The check fails a pull request whose replay could not run on the base: pytest stopped, did not start or wrote no complete JUnit report. It also fails a pull request whose replay hit the host path guard. Such a failure proves nothing about the fix. In both cases, merge the change to the test harness or the dependencies first, in a pull request that is not a fix. Then replay the fix against the new base. A failure at the network, process or keyring guard is no such case. A changed test can fail there on the base and prove a fix. A test counts as changed when its function has another syntax tree than the function of the same name at the merge base. A test also counts as changed when the rest of its file has another syntax tree. The rest of a file is its imports, helpers and fixtures. So a comment or a blank line changes no test. A changed helper makes every test of its file changed. The check reads the changed test files only. A change to a shared file, such as `tests/conftest.py` or a module of `tests/support/`, can make an unchanged test fail on the base. Then the replay fails, and you merge that change first in a pull request that is not a fix. No line in the body changes the result. A changed test that only fails to collect on the base counts as errored.
- **Helper Scripts**: A committed helper script goes in `scripts/` as a PEP 723 file, and Ruff checks it. The pull request that adds the first script adds `scripts` to the mypy and Bandit targets. Scratch scripts stay untracked under `.data/agent/scratch/`.
- **Documentation Synchronization**:
  Run documentation introspection after any command or option change:
  ```bash
  uv run devops docs generate --sync-readme
  ```
  Every Markdown file belongs to exactly one class of the documentation inventory (`CONST_DOCS_INVENTORY` in `src/devops_cli/config/constants.py`), so a pull request that adds a document lists it there. `devops docs check` resolves the `devops` command lines of every hand-written and prompt document against the live command tree, so a command named in prose is a command that exists.

---

## 5. Naming

This table holds the naming rules of the project. Each rule names the check that enforces it. A rule with no check is a convention: follow it, and expect a reviewer to ask for it.

| Artifact | Form | Check |
| :--- | :--- | :--- |
| Branch | `<type>/<issue>-<slug>` | The `no-commit-to-branch` pre-commit hook refuses a commit on a branch that breaks the form. `devops repos worktrees add` makes a branch in this form. |
| Pull request title and commit subject | `<type>(<scope>): <summary>`, with a summary of at most 60 characters (an emoji counts as two) | The `Semantic PR title` check for the title: its form, its scope and the length of its summary. `devops pr create` checks the same rules before it opens the pull request. None for a commit on a branch. |
| Change folder | `<issue>-<slug>`, archived as `<YYYY-MM-DD>-<issue>-<slug>` | `devops openspec check` and `tests/test_change_folders.py`. |
| Python module, class, function and variable | PEP 8 | Ruff `N`. |
| Constant | `_<NAME>` in the one module that reads it. `<NAME>` in the `constants.py` of a package when several of its modules read it. `CONST_<NAME>` in `config/constants.py`, or `DEFAULT_<NAME>` for a tunable value in `config/defaults.py`, when modules of two or more packages import it ("Closed Lists and Standard Parsers" above). A `DEFAULT_<NAME>` that a settings field takes as its default is read only in `config/`: a module elsewhere reads the loaded setting, or `setting_default("<key>")` where it has no settings | `tests/invariants/test_source_tree.py` finds each read of a setting's default outside `config/`. |
| Test file and test function | The behavior it checks, in the terms of [CONTEXT.md](CONTEXT.md) ([docs/TESTING.md](docs/TESTING.md#names-and-assertions)) | None. |
| `devops` command and option | Lowercase words joined by hyphens | None. |
| Environment variable | `DEVOPS_CLI_` and the setting's dotted key in upper case, with `_` for `.`. A settings field declares its variable with a `Variable` marker (`src/devops_cli/config/env.py`) and its description with `Field(description=...)`; a credential is one entry of `CREDENTIALS` in the same module | `tests/test_config_declarations.py` holds the set of variables and keyring entries. `devops config show`, `devops config env` and `docs/ENV_VARS.md` are generated from the declarations. |
| Metric | `devops_cli_<name>`; a counter ends in `_total` and no other metric does. Each metric is an entry of `INSTRUMENTS` in `src/devops_cli/telemetry/instruments.py`, sent with `emit()` | `tests/test_telemetry_instruments.py` checks the `_total` suffix, and fails on a metric that a module writes by name or on an `emit()` of an instrument that `INSTRUMENTS` does not hold. |
| Issue label | `<category>/<value>`, from `.github/labels.yml` | `devops gh labels sync`. |
| Decision record | `docs/adr/<NNNN>-<slug>.md` | None. |
| Release tag | `v<major>.<minor>.<patch>` | release-please writes it. Nobody tags by hand. |
| Agent file, worktree and scratch script | Under `.data/agent/`. The worktree of an issue is `.data/agent/worktrees/w-<issue>`. | `.gitignore`. `devops repos worktrees add` makes the worktree, or takes over the staged branch of the issue. |

The parts of a branch name:

- `<type>` is the type of the pull request title: `feat`, `fix`, `perf`, `refactor`, `revert`, `docs`, `test`, `build`, `ci`, `style` or `chore`. `release-please-config.json` lists the same types. Only the first five add a line to the changelog.
- `<issue>` is the number of the one issue that the pull request closes.
- `<slug>` is lowercase words and digits, joined by single hyphens. It is the slug of the change folder.

Start the work on an issue with `devops repos worktrees add <issue> --type <type> --slug <slug>`. The command fetches `origin/main` and creates the worktree `.data/agent/worktrees/w-<issue>` on a branch in the form above. The branch has no upstream, so the first push is `git push -u origin HEAD`. The command refuses the issue when a worktree has a branch for it (whatever the type and the slug), when the directory `w-<issue>` exists, or when `origin` has a branch for it, and its error names the holder. A local branch with no worktree holds nothing. One pushed branch is not a hold: a staged branch, which the App pushed. When `origin` has a branch for the issue, and every commit of it past `origin/main` has the App as author (the login `<service.github_app.slug>[bot]`), the command takes the branch over. A clean merge by a person is left out of this check. A clean merge is a merge commit with two parents whose tree `git merge-tree --write-tree` gives. The "Update branch" button of GitHub writes such a merge. A merge that changed a file or resolved a conflict is not clean. It adds the worktree on that branch with `origin/<branch>` as its upstream, so a plain `git push` goes to the branch, and it reports the number of commits. The same rule takes over the App's commits of a stopped implement run. The command takes `--type` and `--slug` from the staged branch, so both can be left out, and a value that differs from the branch is an error that names the branch. A branch with a commit by any other author that is not a clean merge, a branch with no commit past `origin/main`, and any pushed branch while `service.github_app.slug` is not set stay holds, and the error names the cause. `--dry-run` cannot read `origin`, so it needs `--type` and `--slug`. Before it looks for a holder, the command removes the worktrees of merged work: the ones that `devops repos worktrees prune --confirm` removes, which are clean, not locked, not the current directory, and at the head of a merged pull request. A merged worktree still holds its issue until then. The command names each removed worktree with its size. It goes on and says why when GitHub cannot be read, and `--no-reclaim` skips the step. `devops repos worktrees status` shows the issue of each worktree. After the worktree exists, the command claims the issue for an agent with the label `owner/agent`. If the claim fails, for example when the Service holds the item, the command only warns.

The rule covers the branches that you push to this repository. GitHub makes the branches of bots (`release-please--*` and `renovate/*`), and nobody commits on them locally. `devops branches jira` and `devops scan fix` name branches of other repositories.

---

## 6. Routine Tasks Checklist

Before opening a pull request or handing off work, verify all applicable tasks from [`docs/ROUTINE_TASKS.md`](docs/ROUTINE_TASKS.md) have been completed.
