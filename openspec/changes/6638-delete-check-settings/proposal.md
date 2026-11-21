# Proposal: #6638

## Why
#6638: `check_settings` scans the git settings of the checkout before each call of `OriginGit` that holds the token, and when each turn of the agent ends. It refuses keys, attribute drivers and an alternates file, and the item stops with the class `git_config`.

The scan protects no call with the token. `OriginGit` runs each fetch and push in a new git folder with `GIT_CONFIG_GLOBAL=/dev/null` and `GIT_CONFIG_NOSYSTEM=1`, so git reads none of the scanned settings. The scan also has costs: it runs `git ls-files` and `git check-attr` in the checkout, so a `core.fsmonitor` program runs before the scan refuses it, and it refuses blobless clones, Git LFS repositories and the `--shared` evaluation clone. The owner approved the removal of this check on 2026-11-21 (AGENTS.md rule 5).

## What Changes
- Delete `check_settings`, `refused_settings` and their helpers from `git_isolation.py`, and the constants that only they read: `CONST_GIT_ALLOWED_SETTINGS`, `CONST_GIT_ALLOWED_SETTING_PATTERNS`, `CONST_GIT_ATTRIBUTE_DRIVERS`, `CONST_GIT_BUILTIN_DRIVERS`, `CONST_GIT_ATTRIBUTE_STATES`, `CONST_GIT_ALTERNATES_FILE` and the message `implement_git_attribute_refused`.
- Delete the scan after each turn of the agent in `implement_step.py`, and the second sweep of `OriginGit` that ran after the scan.
- Keep `OriginGit`, its isolated configuration, the sweeps, the `shallow` file handling and the URL pin until #3700.
- Keep `GitSettingsError` and the class `git_config` for their one other raiser: a `shallow` file of the clone that is a link or is not a regular file. The stop paths in `implement_run.py` stay for it, and the message of the error names that file.
- Add tests that an `insteadOf`, a `pushInsteadOf`, a `pushurl` and a `pre-push` hook in the hooks folder of the clone get no request and do not run.
- The change is observable: an item no longer stops on a git setting, so the spec `roadmap-implement-runner` gets a delta.

## Capabilities
- `roadmap-implement-runner`: remove the requirement of the scan, and change the requirements of the sweeps, of the checkpoint and stop push, and of the network call.

## Impact
- A target repository with Git LFS, a blobless clone or a driver of its own can use the implement Job.
- The class `git_config` now comes only from a link at the `shallow` file.
- The change fits one pull request.

## Feasibility
- `git_isolation.py` on `origin/main`: `_Folder.call` runs git with `--git-dir` of a new bare folder, `CONST_GIT_ISOLATED_CONFIG_ENV` and an empty `HOME`, so git reads no configuration of the home folder or of the clone.
- A mutation of `_Folder.call` that runs git in the git folder of the clone, with no isolated environment, makes the new `insteadOf` and `pushInsteadOf` tests fail: the push goes to the planted server. With the isolation, they pass.
- `_read_shallow` raises `GitSettingsError` for a link at `shallow`, so the error and the class have a raiser after the deletion.

## Existing Tool Considered
- No tool is needed: the change deletes code. git itself, with `GIT_CONFIG_GLOBAL=/dev/null`, `GIT_CONFIG_NOSYSTEM=1` and a new `--git-dir`, is the control that stays.
- Deleted internal code: `check_settings`, `refused_settings`, `_allowed`, `_refused_keys`, `_driver_refused`, `_refused_attributes`, `_CHECKED_SCOPES`, the `isolated` option of `_git`, six constants and one message.
