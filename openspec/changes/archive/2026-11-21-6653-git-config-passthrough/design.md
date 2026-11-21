# Design

## Decisions
- **Each child of a person gets the keys.** A shell gives the `GIT_CONFIG_*` keys to each child, and `build_subprocess_env` does not know the command. A child such as `uv run devops ...` starts git children of its own, so it needs the keys too.
- **The GitHub App gets none, also with isolation off.** The images set the helper in `/etc/gitconfig`. Until #3700 the shell of the agent can start a process with keys of its own, and the process that holds the token must not give them to git.
- **The keys match by name and case.** git reads only the upper-case names, so `fnmatchcase` with `CONST_GIT_CONFIG_ENV_PATTERNS` matches them, and a lower-case key stays out.
- **The tests start with no such key.** An autouse fixture removes the keys of the devcontainer, so a test gets the same environment in the devcontainer and on a GitHub runner.

## Rejected alternatives
- **Give the keys only to a git child.** `build_subprocess_env` gets no command, and a nested `devops` process or a `uv` child that runs git would lose the helper.
- **Keep the inserted `-c` values (#6479).** They replace the helper that the person configured, and they needed `_command_words` to keep them out of the error text. The owner chose the plain git flow on 2026-11-21.
- **Keep the per-call values of `devops infra` and `deploy-stack`.** The devcontainer keys now reach git, and the images set the same helper in `/etc/gitconfig`, so the values add nothing.
