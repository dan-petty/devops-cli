# Design

## Decisions

- The fetch in `render_at_revision` takes the `-c` values of `CONST_GIT_GITHUB_CREDENTIAL_CONFIG` after the SSH option and before the subcommand `fetch`. git reads command-line config last, so the empty helper value clears the helpers of the config files for github.com, and gh is the only helper. This is the same form that `infra/repo_tree.py` uses.
- The values go on every fetch, not only on a fetch from github.com. The config key names `https://github.com`, so git applies the helper only to that host. A check of the URL in our code would repeat the URL match of git.
- The pairs are built inline, as `infra/repo_tree.py` and `roadmap/implement/git_isolation.py` do. Plan step 15 of #5120 deletes this module, so a shared helper for one more caller does not pay back.
- The test records the commands at the runner edge. The process fake replaces the whole runner, so a test cannot see the GH_TOKEN pin. The test asserts that `git_reaches_remote` is true for the fetch, and the tests of the process runner cover the pin.

## Rejected alternatives

- Put the token in the URL (`https://x-access-token:<token>@github.com/...`). Rejected: git writes the URL into `.git/config` and into error text, and `_stdout` puts the command and the error into the message of `KubernetesContextError`. The helper keeps the token out of argv and out of files.
- Set `GIT_CONFIG_*` keys in the environment of the fetch. Rejected: `build_subprocess_env` does not pass these keys (the docstring of `CONST_GIT_GITHUB_CREDENTIAL_CONFIG`), and the existing requirement "The fetch of an Argo CD revision never asks a question" allows only `GIT_TERMINAL_PROMPT=0` as a git key.
- Prove the fix with `deploy-stack --dry-run`, as the issue says. Rejected: the dry run makes no request and does not call `render_at_revision` (`_render_deploy_stack_dry_run` in `commands/k8s/stack_lifecycle.py`).
