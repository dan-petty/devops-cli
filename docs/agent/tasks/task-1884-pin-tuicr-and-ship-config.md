# Task: Pin tuicr with a no-update-check config template and .tuicrignore (#1884)

**Issue**: [#1884](https://github.com/dan-petty/devops-cli/issues/1884)
**Scope**: type/feature
**Feasibility**: Checked on 2026-10-22 against the public tuicr v0.27.0 release, its source tag and the real installer. The section "Feasibility checks" lists each check and its result.

## Feasibility checks

- A search of `src/devops_cli/ui/` for `diff` finds no diff widget. `devops pr diff` prints text.
- The four digests that the GitHub release API gives for the macOS and musl Linux archives equal the four hashes in `tools.lock`.
- The release has seven assets and no checksum file. Its `release.yml` has no step for a checksum, a signature or an attestation (a search of the file at the tag).
- `devops install-tools --tool tuicr` installed the linux-amd64 build into a scratch directory with a scratch data root. The installer refused no download. `--check` exited 0, and `tuicr --version` printed `tuicr 0.27.0`.
- The config keys come from `src/config/mod.rs` in the tag: `no_update_check`, `comment_types` with `id`, `label`, `definition` and `color`, and `[export] intro`.
- With the template as config, `tuicr review add --type bogus` printed `known types: issue, question, nit`. With no config, the same command printed no warning.
- In a scratch repository with four changed files, `.tuicrignore` changed the file count of the session from 5 to 3. The five entries are the four files and the commit message. The three that stay are `a.py`, `CHANGELOG.md` and the commit message.
- `tuicr review list` and `tuicr review comments` print JSON with the fields that the SDLC bullet names.
- `tuicr review comments` prints `"comment_type": "none"` for a comment with no type. The field is never empty or absent.
- `tuicr review list` prints `"active": true` only while a tuicr process is open on the session. In a pseudo-terminal run on 2026-10-22, it printed `false` after tuicr quit.
- `tuicr --help` lists the subcommands `tui`, `pr`, `review` and `update`. A start with options only, such as `tuicr -r <range>`, opens the interface.
- No agent opened the review interface in a terminal. A two-second start in a pseudo-terminal made the scratch session.

## Description

A person who reviews the diff of an agent had no review interface. The dashboard has no diff widget, and `devops pr diff` prints text. The person pasted comments into a chat by hand, and the agent got no line numbers and no comment ids. An open tool fills this gap. It is tuicr, a terminal program that shows a diff and lets a person add typed comments on lines. It exports them as text or as JSON.

Nothing is built. The open tool is tuicr, and this change is a lock pin, a config template and text.

This change adds:

- **The pin.** The `[binary.tuicr]` block in `src/devops_cli/tools_lock/tools.lock` locks version 0.27.0. It holds a SHA-256 for macOS and Linux, each on amd64 and arm64. The Linux builds are the static `musl` archives. The header of the lock says that the asset `digest` is the only source of the hashes. It also says that `curl | sh`, `cargo install`, `brew` and `tuicr update` skip the pin. `devops install-tools` and the post-create step install it like every other locked tool.
- **The config template.** `.devops/tuicr.config.toml` sets `no_update_check = true`, because tuicr otherwise calls `crates.io` at start. It defines the comment types `issue`, `question` and `nit`, each with a definition that the export legend shows to the agent. It sets a short `[export] intro`. A person copies the file once to `~/.config/tuicr/config.toml`. The installer does not write it, because AGENTS.md requires a backup before an edit outside the workspace.
- **The ignore file.** `.tuicrignore` hides `docs/commands/*.md` and `docs/CLI_REFERENCE.md`, which `devops docs check` already checks. Lockfiles, the tools lock, `CHANGELOG.md` and `docs/ROADMAP.md` stay visible. A change to one of them is a change to a trust root or to a rule.
- **The tests.** `tests/test_tuicr_config.py` has three tests. The template sets `no_update_check` to `true`. Every comment type has a definition, and the ids are `issue`, `question` and `nit`. Every pattern of `.tuicrignore` is in the generated class of `CONST_DOCS_INVENTORY`. `tests/test_tools_lock.py` requires `tuicr` in the lock. `.tuicrignore` is in `[tool.mutmut] also_copy`, because the new tests read it from the root of the checkout.
- **The review round.** The "Human Review Round" bullet in Phase 6 of `docs/SDLC.md` gives five steps to an agent. The agent finds the session, reads the JSON and handles the comments by type. Then it replies by comment id and asks for a new session after the commit. The bullet lists the commands that an agent never runs. It repeats that a person records verdicts with `devops review verify`.
- **No skill file.** The review steps are in the SDLC bullet and not in a skill. `.gitignore` ignores every folder under `.claude/skills/` except `openspec-*`, and ADR 0010 and `tests/test_openspec_scaffold.py` keep it so.
- **The docs.** `docs/DEVCONTAINER_USAGE.md` says how to start tuicr, how to copy the template, and what an agent never runs. `docs/VISION.md` item 15 now says that pinned open tools make the terminal canvas: `k9s`, `gh-dash` and `tuicr`. It also says that `devops dashboard` covers only what no open tool covers. `openspec/config.yaml` lets a change that alters code end with the person step to review the diff in tuicr.

The upkeep of a bump is one version, four URLs and four hashes. tuicr is below 1.0 and has one main maintainer. This change relies only on the documented CLI JSON, never on the session file. If the project stops, the pin stays at the last good release.

## Acceptance Criteria

- [x] `tools.lock` pins tuicr 0.27.0 with a SHA-256 and an `https` URL for each platform: `test_the_packaged_lock_holds_every_tool_install_tools_installs` and `test_every_binary_build_is_an_https_url_with_a_sha256`.
- [x] The template keeps the update check off: `test_the_template_keeps_the_update_check_off`.
- [x] Every comment type of the template has a definition for the legend: `test_every_comment_type_of_the_template_has_a_definition_for_the_legend`.
- [x] The ignore file hides only generated documents: `test_the_ignore_file_hides_only_generated_documents`.
- [x] `tests/test_tuicr_config.py` and `tests/test_tools_lock.py` pass. They run offline and never start tuicr. `devops ci` passes in the pre-push hook before the push.
- [x] `docs/SDLC.md` Phase 6 describes the human review round, `docs/VISION.md` item 15 describes the open-tool canvas, and `docs/DEVCONTAINER_USAGE.md` says how to start tuicr.
- [x] `changelog.d/1884.md` records the change. `CHANGELOG.md` and `docs/ROADMAP.md` are not edited.
- [x] The entry `Bash(tuicr *)` is in `.claude/settings.json`. A person applied it, because an agent must not edit its own permission file. It allows every `tuicr` command without a prompt.
- Not done: the deny entries for the start and write forms of `tuicr` and for `gh-dash`. A person decided on 2026-10-22 to add no deny entry. The settings allow the interface, `tuicr review clear`, `clearc`, `delete` and `add`, `tuicr update` and `tuicr pr`. No entry covers `gh-dash`, so an agent run of it prompts like any other command that no entry covers. The rule that an agent never starts `tuicr` or `gh-dash` stays in `docs/DEVCONTAINER_USAGE.md` and in `docs/SDLC.md` Phase 6. The settings do not enforce it.
- Pending a person: when the GitHub request budget design merges, compare its settings entries with `.claude/settings.json`. The file must hold one set and no duplicate.
- Pending a person: run `devops install-tools --tool tuicr`, then `devops install-tools --check`. The check exits 0 when every tool has its locked version.
- Pending a person: copy the template with `mkdir -p ~/.config/tuicr && cp .devops/tuicr.config.toml ~/.config/tuicr/config.toml`. If that file exists, copy it first to `~/.config/tuicr/config.toml.bak-<YYYYMMDD-HHMMSS>`.
- Pending a person: run one real review. In a worktree of an agent, run `tuicr -r <release-branch>..HEAD`, add a comment, press `y` and check the export. In another terminal, run `tuicr review list --repo <worktree>` and `tuicr review comments --repo <worktree> --session <slug>`. Check the JSON fields `id`, `location`, `path`, `start_line`, `end_line`, `side`, `comment_type`, `author`, `lifecycle_state`, `created_at` and `content`. Judge the VS Code terminal. The clipboard (OSC 52) and Shift-Enter are not verified (issue 782 of the tuicr repository).
- Pending a person: run one agent round. Ask an agent to address the comments of that review, with the "Human Review Round" bullet of `docs/SDLC.md`. Keep tuicr open during the round, or give the agent the session slug, because `"active"` is true only while tuicr is open. Check that the entry `Bash(tuicr *)` stops the permission prompt for the `tuicr review` commands. Report what failed.

## Deliverables

- [x] `src/devops_cli/tools_lock/tools.lock`: the `[binary.tuicr]` block and a note in the header.
- [x] `.devops/tuicr.config.toml` and `.tuicrignore`.
- [x] `tests/test_tuicr_config.py`.
- [x] `tests/test_tools_lock.py`: `tuicr` in the required tools.
- [x] `pyproject.toml`: `.tuicrignore` in `[tool.mutmut] also_copy`.
- [x] `docs/DEVCONTAINER_USAGE.md`, `docs/SDLC.md` and `docs/VISION.md`.
- [x] `openspec/config.yaml`: one sentence in the `tasks` rule.
- [x] `changelog.d/1884.md`.
