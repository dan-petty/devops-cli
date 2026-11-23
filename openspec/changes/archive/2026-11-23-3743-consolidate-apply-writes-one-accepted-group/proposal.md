# Proposal

## Why

The consolidate flow ends at a local plan of proposed groups, and #3743 needs the last step: a person accepts one group, and one command applies exactly that group as the person's login with `--confirm`. Nothing applies a plan today, so an accepted group changes nothing on GitHub, and the writes of a group must stay inside its anchor and its members.

## What Changes

- Add `--apply <group-id>` to `devops roadmap consolidate`, with its help in `RoadmapCommandHelp`, a refusal without `--confirm` and a refusal of a group id that the latest plan does not hold.
- Add `src/devops_cli/roadmap/consolidate_apply.py`, which reads the latest plan through `last_plan` and dispatches one writer by the group shape.
- Add `add_blocked_by(blocked, blocker)` to the store protocol, the GitHub store and the memory store, with one contract test on each store.
- Write the anchor body through `write_issue_body` with one marked section headed `## Consolidated from #<a>, #<b>`, and replace that section on a second apply.
- Copy each member's `## Acceptance criteria` and `## Key questions` sections byte for byte and add the root cause as plain text, with no model call.
- Close each member of a merge group as not planned with one `Merged into #<anchor>: <one line>` comment.
- Add the sub-issue links or the blocked-by links of a parent group, and one fixed-template comment on the anchor that lists the children in the plan's order.
- Close the member of a `close-as-duplicate` group with `close` and `CloseReason.DUPLICATE` once the anchor is closed as completed, and post one comment that names the anchor.
- Post one fixed-template comment on each member of a link-only group.
- Set the anchor's Priority to the highest member Priority only when the anchor holds no Priority that its job record does not hold, and never write a milestone.
- Regenerate `docs/commands/roadmap.md` and edit `docs/roadmap/consolidate.md` for the new options.
- The change carries a spec delta because a `devops` command, its options and the GitHub writes that it makes are observable behavior.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `roadmap-consolidate-apply`: apply-option, unknown-group, merge-section, merge-content, merge-member-close, merge-reapply, parent-link-kind, blocked-by-store, parent-anchor-comment, duplicate-close, link-only, priority-placement, injection, command-docs

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/stores/github_store.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/consolidate.py`, `src/devops_cli/roadmap/consolidate_apply.py`
- Documents: `docs/commands/roadmap.md`, `docs/roadmap/consolidate.md`
- Tests: `tests/support/fakes/roadmap_store.py`, `tests/roadmap/stores/test_roadmap_store_contract.py`, `tests/roadmap/test_roadmap_consolidate_apply.py`

## Feasibility

- The premise of the issue is that the consolidate command plans groups and applies nothing. `src/devops_cli/commands/roadmap.py:def consolidate_cmd` declares `--repo`, `--ref`, `--limit`, `--decline`, `--dry-run` and `--confirm` and no `--apply`, and the option table of `docs/commands/roadmap.md` lists the same six, so the option is missing and can be created.
- `file_symbols` on `src/devops_cli/roadmap/stores/store.py` listed `write_issue_body`, `read_issue_body`, `add_sub_issue`, `blocked_by`, `comment`, `close`, `set_field` and `issue`, so every write of the apply is a store method that the protocol already holds.
- The probe line `The path `src/devops_cli/commands/roadmap.py` is a file of the staging commit.` confirms the command module, and `The path `src/devops_cli/lang/en/help.py` is a file of the staging commit.` confirms the help catalog that holds `src/devops_cli/lang/en/help.py:class RoadmapCommandHelp`.
- The probe line `The path `src/devops_cli/roadmap/stores/github_store.py` is a file of the staging commit.` confirms the GitHub store, and `The path `tests/support/fakes/roadmap_store.py` is a file of the staging commit.` confirms the memory store that the tests use.
- The probe line `CloseReason` defines the field `DUPLICATE` at src/devops_cli/roadmap/stores/store.py:103` gives the staged value of the constant that the duplicate close relies on: `CloseReason.DUPLICATE` is `duplicate`.
- The probe line `The path `docs/commands/roadmap.md` is a file of the staging commit.` confirms the generated command page, and `The path `openspec/changes/archive/2026-11-06-1127-consolidate-shortlist/proposal.md` is a file of the staging commit.` confirms the shortlist plan that the apply reads.
- `file_symbols` on `src/devops_cli/roadmap/consolidate.py` listed `Plan`, `Group`, `PendingClose`, `read_plan`, `plan_path` and `_last_plan`, so part 2 of the flow is in the staged tree and the apply reads the plan file that it writes.
- `search_code` for `_last_plan` returned only `src/devops_cli/roadmap/consolidate.py`, at its definition and two call sites, so promoting it to `last_plan` touches one file.
- `search_code` for `add_sub_issue` returned `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/stores/github_store.py`, `tests/support/fakes/roadmap_store.py`, `tests/roadmap/stores/test_roadmap_store_contract.py`, `src/devops_cli/roadmap/intake/intake.py` and `src/devops_cli/roadmap/request_plan.py`.
- `search_code` for `Shape.PARENT` returned `src/devops_cli/roadmap/consolidate.py`, whose `_ALLOWED` map allows only `Action.CHILD` for that shape and records no link kind, so the apply decides the link kind from the board and not from a field that the plan does not hold.
- `search_code` for `state_reason` returned `openspec/changes/archive/2026-10-29-1658-issues-close-reason/proposal.md`, which records that the upstream REST reference lists `not_planned`, `duplicate`, `reopened` and `null` as the values of `state_reason`, so the duplicate close uses `CloseReason.DUPLICATE`.
- `search_code` for `def generate` returned `src/devops_cli/commands/docs.py:def generate`, whose options are `--output-dir`, `--format` and `--check`, so the plan runs `uv run devops docs generate` and no `--sync-readme`.
- `search_code` for `consolidate_confirm` returned `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py` and `src/devops_cli/commands/roadmap.py`, where `--confirm` with no `--decline` is refused today, so the guard changes with the new option.
- `read_file` of `docs/roadmap/consolidate.md` showed its options table and its sentence that the apply step of #3743 will act on the plan, so that page takes the new option.
- `read_file` of `tests/ai/mcp/test_mcp_roadmap_tools.py` showed `test_roadmap_consolidate_is_a_read_only_mirror_of_the_plan_run`, which asserts that the MCP tool passes none of `--apply`, `--confirm` and `--decline`, so the tool keeps its four parameters.
- `read_file` of `tests/roadmap/stores/test_roadmap_store_contract.py` showed `test_add_sub_issue_links_child_to_parent` over the `world` fixture, so the blocked-by contract case follows the same shape and runs against both stores.
- The first checks that the implementation runs against the real system: `uv run devops roadmap consolidate --help` lists the two new options; `uv run devops ci test tests/roadmap/stores/test_roadmap_store_contract.py` passes the blocked-by contract case; `uv run devops ci test tests/roadmap/test_roadmap_consolidate_apply.py` passes the apply cases offline; `uv run devops docs generate --check` reports the generated pages up to date.
- `store.issue(number)` needs a client of the GitHub service in production, and every test passes the memory store of `tests/support/fakes/roadmap_store.py` in its place.
- `store.read_issue_body(number)` needs a client of the GitHub service in production, and every test passes the memory store in its place.
- `store.write_issue_body(number, body)` needs a client of the GitHub service in production, and every test passes the memory store in its place.
- `store.close(number, reason, comment=...)` needs a client of the GitHub service in production, and every test passes the memory store in its place.
- `store.comment(number, body)` needs a client of the GitHub service in production, and every test passes the memory store in its place.
- `store.add_sub_issue(parent, child)` needs a client of the GitHub service in production, and every test passes the memory store in its place.
- `store.add_blocked_by(blocked, blocker)` needs a client of the GitHub service in production, and every test passes the memory store in its place.
- `store.set_field(item, ItemField.PRIORITY, value)` needs a client of the GitHub service in production, and every test passes the memory store in its place.
- `last_plan(directory, repo)` reads one local file under the data directory: it needs no checkout, no client and no network.
- The commands that the plan introduces are `uv run devops ci test <path>` and `uv run devops docs generate`; `uv` and `devops` are tools of the runner image, no program of the NOT_IN_RUNNER list is needed, and the pod runs with `runAsNonRoot`, `readOnlyRootFilesystem: true`, `allowPrivilegeEscalation: false` and `capabilities.drop: ALL`.
- The new tests double the store and the plan file only: no test reaches a network, a cluster or a real scanner, and each new test takes at most 1 s.

## Existing Tool Considered

GitHub's REST API covers every write that the command needs: the body edit through `PATCH /repos/{owner}/{repo}/issues/{number}`, the close with `state_reason`, the sub-issue link, the blocked-by dependency and the issue comment. The change calls them through the existing store, the `devops gh` pacing and the memory store, so it adopts no new dependency and builds only two thin store and apply modules.

## Dependencies

- Pull request #5939 shares `docs/commands/roadmap.md` and `src/devops_cli/lang/en/help.py`, so its help text and the regenerated command page can conflict with the two new option rows.
- Pull request #5940 shares `docs/commands/roadmap.md` and `src/devops_cli/lang/en/help.py`, so its help text and the regenerated command page can conflict with the two new option rows.
- Pull request #5946 shares `docs/commands/roadmap.md` and `src/devops_cli/lang/en/help.py`, so its help text and the regenerated command page can conflict with the two new option rows.
