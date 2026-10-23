# Task: Pin gh-dash and ship .gh-dash.yml for the oldest-first PR queue and issue triage (#1882)

**Issue**: [#1882](https://github.com/dan-petty/devops-cli/issues/1882)
**Scope**: type/feature, scope/github, scope/cli
**Feasibility**: Checked on 2026-10-22 against the public gh-dash v4.26.2 release and the real installer. The four hashes in `tools.lock` equal the SHA-256 of the release assets, their GitHub `digest` and `checksums.txt`. The 14 vendored schema files equal the files of `https://gh-dash.dev/schema.json` and the output of the generators `docs/src/pages/schema*.json.ts` in the v4.26.2 tag, run with Node. `devops install-tools --tool gh-dash` installed the linux-amd64 build in a scratch directory, and `--check` exited 0. The icon claims come from the v4.26.2 sources `internal/tui/constants/constants.go` and `internal/config/parser.go`. No agent started gh-dash.

## Description

A person who wants the oldest-first pull request queue, or issue triage, in a terminal had no working tool. The dashboard GitHub tab never loaded, because its queries ask GitHub for a field that does not exist. An open tool does this job: gh-dash, a terminal dashboard where each tab is a GitHub search filter.

This change adds:

- **The pin.** The `[binary.gh-dash]` block in `src/devops_cli/tools_lock/tools.lock` locks version 4.26.2 with a SHA-256 for linux and darwin on amd64 and arm64. The header of the lock says how a bump works. `devops install-tools` and the post-create step install it like every other locked tool.
- **The tabs.** `.gh-dash.yml` at the root of the clone has four pull request tabs: Queue, Failing CI, Needs review and Drafts. Each tab has `sort:created-asc`. The file has three issue tabs: Triage and quality, P0 and P1, and No milestone. It has one notification section for unread review requests, limited to 5. It refreshes every 60 minutes and starts with the preview closed.
- **The keys.** The keys `w`, `T`, `D` and `d` run `devops pr monitor`, `checks`, `threads list` and `diff`. They use only `{{.PrNumber}}` and `{{.RepoName}}`.
- **The icons.** The config hides the cells that gh-dash draws as Nerd Font glyphs: the state, review and CI cells, and the author and creator icons. It sets `showAuthorIcons: false`. The tabs Failing CI, Needs review and Drafts carry the same facts as filters. The file holds only ASCII and sets no glyph. gh-dash still draws other icons with Nerd Font glyphs, in its preview pane, its notification rows and some column headers.
- **The schema.** `tests/fixtures/gh_dash_schema/` holds the 14 JSON files that gh-dash publishes for v4.26.2, with its MIT `LICENSE.txt` and a `VERSION` file.
- **The schema tests.** `tests/test_gh_dash_config.py` checks the config against the schema, with unknown keys forbidden in every object. It adds the keys that the gh-dash parser reads and the published schema lacks. It holds four negative controls. It checks that the schema `VERSION` equals the pin. `tests/test_tools_lock.py` requires `gh-dash` in the lock.
- **The config tests.** The same file checks that every pull request tab sorts oldest first. It checks that the triage tab filters like the "Triage & Quality Table" view of the project board. It checks that a key uses only safe template values. It checks that each key command resolves in the real command tree. It checks that the config holds only ASCII and hides every glyph cell.
- **The docs.** `docs/DEVCONTAINER_USAGE.md` says how to start gh-dash and what its first start writes. It says that gh-dash sends one release-check request. It says that its write keys stay active with the token of the person. It names the icons that still need a Nerd Font.
- **Mutation testing.** `.gh-dash.yml` is in `[tool.mutmut] also_copy`, because the new tests read it from the root of the checkout.

The GraphQL cost of gh-dash depends on two config values: `defaults.refetchIntervalMinutes` and `defaults.preview.open`. [#1918](https://github.com/dan-petty/devops-cli/issues/1918) sets them to 60 and `false`. With these values, gh-dash costs 7 GraphQL points at start and 5 points an hour. The first config, with a refresh every 15 minutes and the preview open, cost 9 points at start and about 28 points an hour. The first text of this task file said about 20 points an hour, and the source of gh-dash 4.26.2 does not support that number. The old tab polled every 60 seconds.

The source, the study and one measurement give these numbers:

- **Request counts, from the source.** At start, gh-dash reads the login (1 point) and checks its latest release on `dlvhdr/gh-dash` (1 point, a GraphQL request). It fetches only the sections of the start view. A refresh fetches every section of the view on screen (`internal/tui/ui.go:732-735`). An open preview fetches the detail of the selected row when a section loads and when a person selects a row. A closed preview fetches no detail.
- **Cost of one request, from the study.** Three `rateLimit(dryRun: true)` calls gave these costs. A pull request section costs 1 point at `limit: 20` and 2 points at `limit: 50`. An issue section costs about 1 point. The detail of a row costs 2 points. This change does not measure them again.
- **Totals, from the counts and the costs.** The start view has Queue at `limit: 50` (2 points) and three sections at `limit: 20` (3 points), so the sections cost 5 points. With the login and the release check, the start costs 7 points. With the preview open, it costs 9 points. A refresh costs 5 points, or 7 points with the preview open. At 4 refreshes an hour with the preview open, the cost is 28 points an hour. At 1 refresh an hour with the preview closed, it is 5 points an hour.
- **One measurement, with no assigned cause.** A person measured +124 GraphQL points in 22 seconds at the first start with the first config. The first config explains 9 of these points, and the measuring command `devops gh rate-limit` adds 1 point. A later count of the log lines matches the computed cost of about 9 points. The quota counters are shared with every other tool that uses the token, so nobody can assign the jump to gh-dash. [#1918](https://github.com/dan-petty/devops-cli/issues/1918) holds the count of the log lines and the steps to measure again.

## Acceptance Criteria

- [x] `tools.lock` pins gh-dash 4.26.2 with a SHA-256 and an `https` URL for each platform: `test_the_packaged_lock_holds_every_tool_install_tools_installs` and `test_every_binary_build_is_an_https_url_with_a_sha256`.
- [x] `devops install-tools --tool gh-dash` installs the pinned build, and `devops install-tools --check` exits 0.
- [x] The shipped config breaks no rule of the strict schema, and four defects each fail it: `test_the_shipped_config_breaks_no_rule_of_the_strict_schema` and `test_the_strict_schema_refuses_a_misspelt_or_missing_key`.
- [x] The vendored schema is the schema of the pinned version: `test_the_vendored_schema_is_the_schema_of_the_pinned_gh_dash`.
- [x] Every pull request tab lists the oldest pull request first: `test_every_pr_section_lists_the_oldest_pull_request_first`.
- [x] The triage tab has the filter of the board view: `test_the_triage_section_filters_like_the_triage_view_of_the_board`.
- [x] A key command uses no template value that can hold shell syntax, and its first step is a real `devops` command: `test_a_key_binding_names_no_template_value_that_can_hold_shell_syntax` and `test_every_key_binding_runs_a_devops_command_that_exists`.
- [x] The config holds only ASCII and sets no glyph: `test_the_shipped_config_holds_only_ascii`.
- [x] The config hides every glyph cell that the schema lets it hide: `test_the_shipped_config_hides_every_glyph_cell_the_schema_lets_it_hide`.
- [x] `tests/test_gh_dash_config.py` and `tests/test_tools_lock.py` pass. They run offline and never start gh-dash. `devops ci` passes in the pre-push hook before the push.
- [x] `changelog.d/1882.md` records the change. `CHANGELOG.md` and `docs/ROADMAP.md` are not edited.
- [x] The docs say how to start gh-dash: `docs/DEVCONTAINER_USAGE.md`.
- Not done: the permission entry that stops an agent from starting gh-dash. A person decided on 2026-10-22 to add no deny entry to `.claude/settings.json`, here and in [#1884](https://github.com/dan-petty/devops-cli/issues/1884). No entry covers `gh-dash`, so an agent run of it prompts like any other command that no entry covers. The sentence "Agents never start `gh-dash`." stays in `docs/DEVCONTAINER_USAGE.md` as a rule of the docs. The settings do not enforce it.
- Pending a person: run `devops install-tools --tool gh-dash`, then `devops install-tools --check`. The check prints that every tool is linked at its locked version and exits 0.
- Pending a person: at the root of the clone, run `gh-dash --config .gh-dash.yml` with your own token. Check that four pull request tabs, three issue tabs and one notification tab show. Check that Queue lists the oldest pull request first. Check that `w`, `T`, `D` and `d` run the devops commands and return to gh-dash. Check how the terminal shows the icons in the preview pane, the notification rows and the column headers.
- Pending a person: measure the GraphQL cost of gh-dash again. The steps are in [#1918](https://github.com/dan-petty/devops-cli/issues/1918): count the lines of `debug.log`, and do not read the quota counters. The computed cost is 7 points at start, with 2 more points for each row you select with the preview open.
- Pending a person: say whether you use `GH_DASH_CONFIG` or a global gh-dash config. Say whether the terminal on the host has a Nerd Font.
- Pending a person: file each upstream gh-dash issue by hand. Find each defect without an LLM, because `AI_POLICY.md` of gh-dash bans contributions that an LLM wrote or found.

## Deliverables

- [x] `src/devops_cli/tools_lock/tools.lock`: the `[binary.gh-dash]` block and a note in the header.
- [x] `.gh-dash.yml`.
- [x] `tests/fixtures/gh_dash_schema/` and `tests/test_gh_dash_config.py`.
- [x] `tests/test_tools_lock.py`: `gh-dash` in the required tools.
- [x] `pyproject.toml`: `.gh-dash.yml` in `[tool.mutmut] also_copy`.
- [x] `docs/DEVCONTAINER_USAGE.md`.
- [x] `changelog.d/1882.md`.
- Deleting the dashboard GitHub tab: moved to #1883.
