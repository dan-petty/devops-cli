# Design

## Decisions

- **Run the install from `worktrees_add` after `add_worktree` returns, not inside `add_worktree`.**: The command decides what a new worktree gets, and its report names the worktree of both the create path and the take-over path, as `src/devops_cli/git/worktree_add.py:class WorktreeAddReport` shows.
- **Check `package-lock.json` in the new worktree, not in the clone.**: The gate reads the binary of the checkout, so the folder that needs `node_modules` is the new worktree, as `src/devops_cli/openspec/tool.py:def installed_program` shows.
- **Start no npm process on a dry run.**: A dry run creates no worktree, so there is no folder to install into, as the `dry_run` argument of `src/devops_cli/git/worktree_add.py:def add_worktree` shows.
- **Warn and keep the worktree when the install fails.**: The worktree is the work of the command and stays usable, and the next gate run names the install with the locked version, at `src/devops_cli/openspec/gate.py:def version_finding`.
- **Return the warning text from the helper and print it in the command with `print_warning`.**: The helper writes nothing to the console, so a test asserts its text, and the command already warns that way in `src/devops_cli/commands/repos.py:def _render_claim`.
- **Answer `git` with `git_for_real` and `npm` with the process fake in the new tests.**: The test repository is real and its origin is a bare repository in `tmp_path`, so git runs offline, and the fake records the npm call, as `tests/support/implement_step.py:def git_for_real` and `tests/support/fakes/process.py:def process_fake` show.
- **Add the new warning message beside `worktrees_add_created` in the message catalog.**: The worktree add messages form one block of the catalog at `src/devops_cli/lang/en/messages.py:class RepoMessages`, where the next message sits at `src/devops_cli/lang/en/messages.py:656:worktrees_add_created: str = "Created worktree {path} on branch {branch}."`, and `src/devops_cli/commands/repos.py:def _render_claim` shows that the command formats its warnings from that block.

## Rejected alternatives

- **Call `bootstrap_checkout` of the roadmap runner tools from the command.**: `src/devops_cli/roadmap/runner_tools.py:def bootstrap_checkout` builds the whole coder environment, the `uv sync` included, and it raises on a failure, while the command needs one npm line and a warning.
- **Run `npm install --no-save --ignore-scripts`, the form that the bootstrap uses for an existing branch.**: `src/devops_cli/roadmap/runner_tools.py:def bootstrap_checkout` takes `locked` and runs `install --no-save` without it, which accepts a stale lock; the new worktree needs the locked form, which installs `@fission-ai/openspec` 2.2.0 of `package-lock.json`.
- **Let the gate install the tools when the binary is missing.**: `src/devops_cli/openspec/gate.py:def version_finding` only runs the tool and reports its version, and a check must not write into the checkout that it checks.
- **Run real npm in the test and assert the openspec binary of the worktree.**: `tests/support/fakes/process.py:def process_fake` installs the fake process runner for every child, so a test reaches no registry, and `tests/support/implement_step.py:def git_for_real` keeps git real and offline.
- **Test only the helper and leave the command untested.**: `src/devops_cli/commands/repos.py:def worktrees_add` holds the call and the warning, so a helper-only test would prove neither the wiring nor the warning.
