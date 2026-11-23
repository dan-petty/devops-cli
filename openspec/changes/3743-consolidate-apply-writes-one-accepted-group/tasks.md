# Tasks

## 1. Add the blocked-by write to both stores

Kind: behavior. Reads: `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/stores/github_store.py`, `tests/support/fakes/roadmap_store.py`, `tests/roadmap/stores/test_roadmap_store_contract.py`. Changes: `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/stores/github_store.py`, `tests/support/fakes/roadmap_store.py`, `tests/roadmap/stores/test_roadmap_store_contract.py`.

- [x] 1.1 `tests/roadmap/stores/test_roadmap_store_contract.py` gains `test_add_blocked_by_links_the_blocker`, which calls `add_blocked_by` on each store of the `world` fixture and asserts that the GitHub store sends `POST /repos/{owner}/{repo}/issues/{number}/dependencies/blocked_by`
  - Verification: `$ uv run devops ci test tests/roadmap/stores/test_roadmap_store_contract.py` fails on the base
- [x] 1.2 Add `add_blocked_by(self, blocked: int, blocker: int)` to `src/devops_cli/roadmap/stores/store.py:class RoadmapStore` beside `add_sub_issue`. Send `POST /repos/{owner}/{repo}/issues/{number}/dependencies/blocked_by` with the blocker's REST id from `src/devops_cli/roadmap/stores/github_store.py:def add_sub_issue`, inside the existing pacing, and add an args builder beside `src/devops_cli/roadmap/stores/github_store.py:def add_sub_issue_args`. Record the call in `tests/support/fakes/roadmap_store.py` and add the blocker to its `blockers` map. Add one contract case for each store
  - Verification: `$ uv run devops ci test tests/roadmap/stores/test_roadmap_store_contract.py` passes

## 2. Add the consolidate apply dispatch and guards

Kind: behavior. Reads: `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/consolidate.py`, `src/devops_cli/roadmap/stores/store.py`, `tests/support/fakes/roadmap_store.py`, `tests/roadmap/test_roadmap_consolidate.py`. Changes: `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/consolidate.py`, `src/devops_cli/roadmap/consolidate_apply.py` (new), `tests/roadmap/test_roadmap_consolidate_apply.py` (new).

- [x] 2.1 `tests/roadmap/test_roadmap_consolidate_apply.py` gains `test_apply_without_confirm_writes_nothing` and `test_unknown_group_id_writes_nothing`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_consolidate_apply.py` fails on the base
- [x] 2.2 Rename `_last_plan` to `last_plan` in `src/devops_cli/roadmap/consolidate.py` and update its two callers. Add `src/devops_cli/roadmap/consolidate_apply.py` with `group_of(plan, group_id)` and `apply_group(store, plan, group_id, *, confirm)`, which refuse a run with no confirmation and a group id that the plan does not hold, resolve every target from the group and the plan's member list, and dispatch one writer by `Shape`. Write each refusal message in `src/devops_cli/lang/en/messages.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_consolidate_apply.py` passes

## 3. Add the apply option and its documentation

Kind: other. Reads: `src/devops_cli/commands/roadmap.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/roadmap/consolidate_apply.py`, `docs/commands/roadmap.md`, `docs/roadmap/consolidate.md`, `tests/roadmap/test_roadmap_command_help.py`, `tests/commands/test_all_commands_help_dryrun.py`, `tests/commands/test_roadmap_consolidate_cmd.py`, `tests/roadmap/test_roadmap_consolidate_apply.py`. Changes: `src/devops_cli/commands/roadmap.py`, `src/devops_cli/lang/en/help.py`, `docs/commands/roadmap.md`, `docs/roadmap/consolidate.md`, `tests/roadmap/test_roadmap_consolidate_apply.py`.

- [x] 3.1 `tests/roadmap/test_roadmap_consolidate_apply.py` gains `test_generated_command_docs_name_the_apply_option`, reading `docs/commands/roadmap.md`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_consolidate_apply.py` fails on the base
- [x] 3.2 Add `--apply` to `src/devops_cli/commands/roadmap.py:def consolidate_cmd` with its help in `src/devops_cli/lang/en/help.py:class RoadmapCommandHelp`, and let `--confirm` run with `--apply` and no `--decline`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_consolidate_apply.py` passes
- [x] 3.3 Run `uv run devops docs generate` to regenerate `docs/commands/roadmap.md`, and edit `docs/roadmap/consolidate.md` to name `--apply` and `--confirm`, and run `uv run devops docs generate`
  - Verification: `$ uv run devops ci docs` passes

## 4. Apply a merge group

Kind: behavior. Reads: `src/devops_cli/roadmap/consolidate_apply.py`, `src/devops_cli/roadmap/consolidate.py`, `src/devops_cli/roadmap/stores/store.py`, `tests/support/fakes/roadmap_store.py`, `tests/roadmap/test_roadmap_consolidate.py`. Changes: `src/devops_cli/roadmap/consolidate_apply.py`, `tests/roadmap/test_roadmap_consolidate_apply.py`.

- [x] 4.1 `tests/roadmap/test_roadmap_consolidate_apply.py` gains `test_merge_section_is_marked_and_text_outside_stays`, `test_copied_member_sections_and_root_cause`, `test_each_member_is_closed_as_not_planned` and `test_second_apply_replaces_the_section`; the first asserts that `write_issue_body` receives one marked section, and the third asserts one `close` for each member
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_consolidate_apply.py` fails on the base
- [x] 4.2 Write the merge writer in `src/devops_cli/roadmap/consolidate_apply.py`. Read the anchor and the member bodies with `src/devops_cli/roadmap/stores/store.py:def read_issue_body`. Build one section between the two markers, headed `## Consolidated from #<a>, #<b>`, copy the `## Acceptance criteria` and `## Key questions` sections of each member byte for byte, and add the group's root cause as plain text. Replace the text between the markers when the anchor holds them, else append the section, and write the body with `src/devops_cli/roadmap/stores/store.py:def write_issue_body`. Close each member with `src/devops_cli/roadmap/stores/store.py:def close` as not planned and the comment `Merged into #<anchor>: <one line>`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_consolidate_apply.py` passes

## 5. Apply a parent group

Kind: behavior. Reads: `src/devops_cli/roadmap/consolidate_apply.py`, `src/devops_cli/roadmap/consolidate.py`, `src/devops_cli/roadmap/stores/store.py`, `tests/support/fakes/roadmap_store.py`. Changes: `src/devops_cli/roadmap/consolidate_apply.py`, `tests/roadmap/test_roadmap_consolidate_apply.py`.

- [x] 5.1 `tests/roadmap/test_roadmap_consolidate_apply.py` gains `test_parent_sub_issue_links`, `test_parent_blocked_by_links` and `test_parent_anchor_comment_lists_the_children`; the first asserts `add_sub_issue(10, 11)` and `add_sub_issue(10, 12)`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_consolidate_apply.py` fails on the base
- [x] 5.2 Add the parent writer to `src/devops_cli/roadmap/consolidate_apply.py`. Read the anchor and the children with `src/devops_cli/roadmap/stores/store.py:def issue`. Add a sub-issue link with `src/devops_cli/roadmap/stores/store.py:def add_sub_issue` for each child when neither the anchor nor the child holds a milestone, and add a blocked-by link from the child to the anchor with `add_blocked_by` when the anchor holds a milestone. Post one fixed-template comment on the anchor with `src/devops_cli/roadmap/stores/store.py:def comment` that lists the children in the plan's order
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_consolidate_apply.py` passes

## 6. Apply a duplicate and a link-only group

Kind: behavior. Reads: `src/devops_cli/roadmap/consolidate_apply.py`, `src/devops_cli/roadmap/consolidate.py`, `src/devops_cli/roadmap/stores/store.py`, `tests/support/fakes/roadmap_store.py`. Changes: `src/devops_cli/roadmap/consolidate_apply.py`, `tests/roadmap/test_roadmap_consolidate_apply.py`.

- [x] 6.1 `tests/roadmap/test_roadmap_consolidate_apply.py` gains `test_duplicate_close_uses_duplicate_reason`, `test_duplicate_waits_for_the_anchor` and `test_link_only_comments`; the first asserts one `close` with `CloseReason.DUPLICATE` and no `duplicateIssueId` call
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_consolidate_apply.py` fails on the base
- [x] 6.2 Add the duplicate writer and the link-only writer to `src/devops_cli/roadmap/consolidate_apply.py`. Read the anchor with `src/devops_cli/roadmap/stores/store.py:def issue`. When the anchor is not closed as completed, write nothing and report that the group waits for the anchor. Otherwise close each member with `src/devops_cli/roadmap/stores/store.py:def close` and `CloseReason.DUPLICATE`, with one comment that names the anchor. The link-only writer posts one fixed-template comment on each member with `src/devops_cli/roadmap/stores/store.py:def comment`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_consolidate_apply.py` passes

## 7. Place the Priority and guard the write set

Kind: behavior. Reads: `src/devops_cli/roadmap/consolidate_apply.py`, `src/devops_cli/roadmap/consolidate.py`, `src/devops_cli/roadmap/stores/store.py`, `tests/support/fakes/roadmap_store.py`. Changes: `src/devops_cli/roadmap/consolidate_apply.py`, `tests/roadmap/test_roadmap_consolidate_apply.py`.

- [x] 7.1 `tests/roadmap/test_roadmap_consolidate_apply.py` gains `test_priority_moves_to_the_highest_member`, `test_person_priority_and_milestone_stay` and `test_plan_text_with_set_p0_writes_no_p0`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_consolidate_apply.py` fails on the base
- [x] 7.2 In the merge writer of `src/devops_cli/roadmap/consolidate_apply.py`, read the anchor with `src/devops_cli/roadmap/stores/store.py:def item`, compare its Priority with the value in its job record, and set the highest member Priority with `src/devops_cli/roadmap/stores/store.py:def set_field` only when the two agree. Write no milestone. Keep the write set to the anchor and the plan's member numbers, and interpret no plan text
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_consolidate_apply.py` passes

## Criteria

- Group 3: `--apply <group-id>` joins the command of part 2, with help in `RoadmapCommandHelp` and regenerated command docs. It refuses to run without `--confirm`, and refuses a group id that is not in the latest plan.
- Group 4: **merge-into-anchor:** appends a marked section (`<!-- devops-roadmap-consolidate:start -->` to `:end -->`) headed `## Consolidated from #a, #b` to the anchor body through `write_issue_body`. It copies each member's acceptance criteria and key questions verbatim, adds the root cause as plain text, then closes each member as not planned with the comment `Merged into #<anchor>: <one line>`. Text outside the section stays byte-identical.
- Group 5: **parent-task-with-children:** adds sub-issue links with `add_sub_issue`, or blocked-by links when the anchor lands first, and posts one fixed-template comment on the anchor that lists the children and their order. The blocked-by write is a new store operation (`POST /repos/{owner}/{repo}/issues/{number}/dependencies/blocked_by`, upstream REST reference) on the protocol, the GitHub store and the memory store, with contract tests on both stores. The read operation comes from #1127.
- Group 6: **close-as-duplicate:** closes the member with `close`, with one comment naming the anchor. First confirm in the upstream REST reference whether `state_reason: duplicate` is accepted, and use `CloseReason.DUPLICATE` if it is; else use not planned with the comment `Duplicate of #<anchor>`. No GraphQL `duplicateIssueId` call.
- Group 6: **link-only:** posts one fixed-template comment on each member that names the anchor.
- Group 7: Placement: a merge sets the anchor's Priority label to the highest among its members only when no person set the anchor's Priority. It never changes the anchor's milestone.
- Group 6: "Close X when Y merges" proposes the close only after Y is closed as completed.
- Group 7: Injection test: a plan built from a member body that tells the model to set P0 applies with no Priority write to P0 and no write outside the group.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
