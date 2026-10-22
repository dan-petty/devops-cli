# Task: The SSH Key Prefix Matches in One Place, and No Command Uses the Keys of Other Projects (#1920)

**Issue**: [#1920](https://github.com/dan-petty/devops-cli/issues/1920)
**Scope**: scope/cli
**Feasibility**: The author read `src/devops_cli/crypto/ssh_keys.py`, `src/devops_cli/commands/ssh.py` and `_run_post_start_lifecycle` in `src/devops_cli/commands/devcontainer.py` at the release tip. `git grep` over `src` and `tests` found five callers of the key search: `register`, `rotate`, `status`, `list` and the post-start lifecycle of the devcontainer. The author reproduced the defect on the release tip with real key files in a scratch directory. `devops ssh list` with the prefix `devops-cli` showed the keys of three projects, and `status` found the project key only through the retry in `find_newest_key`. After the change, `list` shows the project key, and `list --all` shows three keys. No call to GitHub was made, and the real `~/.ssh` was not read.

## Description
A person asked why `devops ssh list` shows keys that do not carry the project prefix. The prefix of this project is `devops-cli`, with a hyphen. Its key is `devops_cli-id_ed25519-20260831`, with an underscore. `find_newest_key` retried with the other spelling, but `list_keys` did not. `list_keys` found no key and then listed every managed key. So the output held the keys of two other projects.

`find_newest_key` also fell back to the newest key of any project when no key of the prefix existed. Then `register` uploaded a key of another project to the account under the title of the project. `rotate` rotated the same key. `register` also compared the prefix a second time to build the key title. That comparison did not treat a hyphen and an underscore as the same character, so the project key got the title `devops-cli-devops_cli-id_ed25519-20260831`.

`list_managed_keys` now selects keys by prefix, and it is the one place that does. It treats a hyphen and an underscore as the same character. The empty prefix matches the keys that have no prefix. `find_newest_key` has no retry and no `fallback_to_any` parameter. `list_keys` has no fallback. `devops ssh list --all` shows the managed keys of all projects.

`--all` together with `--prefix` is a usage error with exit code 2, also in a dry run. `register` takes the title from the key. A key with a prefix keeps its own file name as the title. A key with no prefix gets the prefix of the project.

When no key of the prefix exists, `register` prints an error and exits with code 1. `rotate` and `status` print a warning and exit with code 0, as before. `list` prints the same warning and adds a tip to use `--all`. The message names the prefix and the key directory. It points to `devops ssh generate`. The change deletes the old messages `no_managed_keys`, `GeneralMessages.no_ssh_key_found` and `SSHErrorMessages.no_ssh_key_found`, because nothing uses them.

`list --all` of a directory with no key prints `no_managed_keys_pattern`. Rich read `[prefix-]` in that message as markup and printed `expected: id_ed25519-YYYYMMDD`. So the message now names `PREFIX-id_ed25519-YYYYMMDD or id_ed25519-YYYYMMDD`.

The post-start lifecycle of the devcontainer keeps its order of keys. It asks `find_newest_key` for the key of the workspace prefix. If it finds none, it asks for the managed key with no prefix, which is the empty prefix. If it finds none, it takes the newest unmanaged `id_` file. It never takes a key of another project.

`devops ssh generate` names keys as before, and no key file on disk is renamed. A rotation from `devops_cli-id_ed25519-20260831` makes `devops-cli-id_ed25519-<date>`. Both spellings match the prefix `devops-cli` from then on.

The open tool for the match is the Python standard library. `str.replace` folds the separator, and `re` already parses the file name. The change adds no code that replaces an open tool.

## Acceptance Criteria
- [x] A prefix with a hyphen and a prefix with an underscore each match the keys of both spellings, and no key of another project (`test_a_prefix_matches_the_keys_of_both_separator_spellings`).
- [x] A prefix with no key finds no key and never the key of another project (`test_a_prefix_with_no_key_finds_no_key_and_never_the_key_of_another_project`). The empty prefix matches only the keys without a prefix (`test_the_empty_prefix_matches_only_the_keys_without_a_prefix`).
- [x] `devops ssh list` shows only the project key, and `--all` shows the keys of all three projects (`test_list_shows_only_the_keys_of_the_project_prefix`, `test_list_with_all_shows_the_keys_of_every_project`).
- [x] `--all` together with `--prefix` is a usage error, also in a dry run (`test_list_refuses_all_together_with_a_prefix`).
- [x] `list --all` of a directory with no managed key names both file name forms (`test_list_with_all_of_a_directory_with_no_managed_key_names_the_expected_file_names`).
- [x] `list` of a prefix with no key shows no key of another project. It names the prefix and points to `devops ssh generate` and to `--all` (`test_list_of_a_project_with_no_key_names_the_prefix_and_never_shows_other_projects`).
- [x] `register` sends the public key of the project key to both GitHub endpoints and no other key. It signs commits with the project key only (`test_register_adds_the_key_of_the_project_to_github`).
- [x] `register` titles a key with a prefix with its own file name. It gives the prefix of the project to a key with no prefix (`test_register_titles_a_key_with_its_own_prefix_or_with_the_prefix_of_the_project`).
- [x] With no key of the prefix, `register` sends no request, exits with code 1 and points to `devops ssh generate` (`test_register_of_a_project_with_no_key_sends_nothing_and_points_to_generate`).
- [x] `rotate` makes the new key with the prefix, reports the project key as the old key and leaves every key of another project (`test_rotate_replaces_the_key_of_the_project_and_leaves_the_keys_of_other_projects`). With no key of the prefix, it changes no file, sends no request and exits with code 0 (`test_rotate_of_a_project_with_no_key_changes_nothing_and_points_to_generate`).
- [x] `status` shows the project key. With no key of the prefix, it warns and exits with code 0 (`test_status_shows_the_key_of_the_project`, `test_status_of_a_project_with_no_key_names_the_prefix_and_points_to_generate`).
- [x] The post-start lifecycle signs with a key of the workspace prefix in either spelling (`test_post_start_honors_workspace_ssh_key_prefix`). With no such key, it signs with the managed key that has no prefix, then with the newest unmanaged key (`test_post_start_signs_with_a_key_without_a_prefix_when_the_workspace_has_none`). It never signs with a key of another project (`test_post_start_does_not_adopt_foreign_prefixed_key`).
- [x] The tests of `register` and `rotate` set `GIT_CONFIG_GLOBAL` to a file under `tmp_path` (`global_git_config`). They leave the global git config of the test worker unchanged, so a later test that runs `git commit` is not affected.
- [x] `docs/CLI_REFERENCE.md`, `docs/commands/ssh.md` and `docs/MCP_TOOLS.md` list the `--all` option. `README.md` and `docs/ROUTINE_TASKS.md` say that `list` shows the keys of the project prefix.
