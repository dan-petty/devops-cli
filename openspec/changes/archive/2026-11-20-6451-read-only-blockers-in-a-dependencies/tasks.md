# Tasks

## 1. Read only a blocker line under Dependencies

Kind: behavior. Reads: `src/devops_cli/roadmap/refine/refine.py`, `tests/roadmap/stage/test_roadmap_stage_selection.py`, `tests/roadmap/test_roadmap_consolidate_shortlist.py`, `tests/roadmap/implement/test_roadmap_implement_selection.py`, `tests/roadmap/refine/test_roadmap_refine_alert.py`. Changes: `src/devops_cli/roadmap/refine/refine.py`, `tests/roadmap/refine/test_roadmap_refine_dependencies.py` (new).
Adds: `_block_blockers`

- [x] 1.1 `tests/roadmap/refine/test_roadmap_refine_dependencies.py::test_body_dependencies_names_only_a_blocker_line` fails on the base: `body_dependencies` returns `[4989]` for a section that holds `None.` and then a paragraph that names `Source: #4989`
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_dependencies.py` fails on the base
- [x] 1.2 Add `_block_blockers(text: str) -> list[int]` to `src/devops_cli/roadmap/refine/refine.py` and change `body_dependencies` to read each inline token of the section through it, with the rule of task 5.1. Leave `_issues` as it is. Write the failing test `test_body_dependencies_names_only_a_blocker_line` first in the new module `tests/roadmap/refine/test_roadmap_refine_dependencies.py`: `None.` and then `Source: #4989` give `[]`, the paragraphs `Part of #5014`, `Child 5 of #4893`, `Related: #4408`, `#4691 needs this item` and `This item blocks #5134 step 6` give `[]`, the list item `- #4989` with `Merge first: #5134` gives `[4989, 5134]`, and the paragraph `#2, #4` gives `[2, 4]`
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_dependencies.py` passes

## 2. File the source under its own heading

Kind: behavior. Reads: `src/devops_cli/roadmap/intake/intake.py`, `src/devops_cli/roadmap/refine/refine.py`, `tests/roadmap/intake/test_roadmap_intake_evidence.py`, `tests/roadmap/intake/test_roadmap_intake_sub_issues.py`, `tests/research/test_sweep.py`, `tests/review/test_review_intake_handoff.py`, `tests/roadmap/intake/test_roadmap_intake_agent_candidates.py`, `tests/roadmap/intake/test_roadmap_intake_checks.py`, `tests/roadmap/intake/test_roadmap_intake_command.py`, `tests/roadmap/intake/test_roadmap_intake_dry_run.py`, `tests/roadmap/intake/test_roadmap_intake_duplicates.py`, `tests/roadmap/intake/test_roadmap_intake_failure_class.py`, `tests/roadmap/intake/test_roadmap_intake_github_requests.py`, `tests/roadmap/intake/test_roadmap_intake_item_changed.py`, `tests/roadmap/intake/test_roadmap_intake_jev.py`, `tests/roadmap/intake/test_roadmap_intake_jev_shadow.py`, `tests/roadmap/intake/test_roadmap_intake_job_result.py`, `tests/roadmap/intake/test_roadmap_intake_labels_file.py`, `tests/roadmap/intake/test_roadmap_intake_model_reply.py`, `tests/roadmap/intake/test_roadmap_intake_shortlist.py`, `tests/roadmap/intake/test_roadmap_intake_untrusted_text.py`, `tests/roadmap/intake/test_roadmap_intake_write_failures.py`, `tests/roadmap/stores/test_roadmap_store_tool_issues.py`, `tests/roadmap/test_job_result.py`, `tests/roadmap/test_roadmap_dry_runs.py`, `tests/roadmap/test_roadmap_retitle.py`, `tests/roadmap/test_roadmap_retitle_type.py`, `tests/roadmap/test_roadmap_run_intake_row.py`, `tests/telemetry/test_roadmap_intake_implement_metrics.py`. Changes: `src/devops_cli/roadmap/intake/intake.py`, `tests/roadmap/intake/test_roadmap_intake_evidence.py`.

- [x] 2.1 `tests/roadmap/intake/test_roadmap_intake_evidence.py::test_a_filed_candidate_names_its_source_under_its_own_heading` fails on the base: `NewCandidate.filed_body` appends `Source: #4989` under a body that ends with `## Dependencies`, and `body_dependencies` of that body returns `[4989]`
  - Verification: `$ uv run devops ci test tests/roadmap/intake/test_roadmap_intake_evidence.py` fails on the base
- [x] 2.2 Change `NewCandidate.filed_body` in `src/devops_cli/roadmap/intake/intake.py` to return the body, then a `## Source` heading, then the source, when the candidate has a source, and the body alone otherwise. Write the failing test `test_a_filed_candidate_names_its_source_under_its_own_heading` first in `tests/roadmap/intake/test_roadmap_intake_evidence.py`, beside the assertion at its line 93: a candidate whose body ends with `## Dependencies` and whose source is `#4989` gets a body that holds the `## Source` heading before `#4989`, and `body_dependencies` of that body returns `[]`. Then change the assertion at line 93 to the `## Source` heading and the source after it
  - Verification: `$ uv run devops ci test tests/roadmap/intake/test_roadmap_intake_evidence.py` passes

## 3. Move the sub-issue test to the new filed-body form

Kind: other. Reads: `tests/roadmap/intake/test_roadmap_intake_sub_issues.py`, `src/devops_cli/roadmap/intake/intake.py`. Changes: `tests/roadmap/intake/test_roadmap_intake_sub_issues.py`.

- [x] 3.1 Change the assertion at line 187 of `tests/roadmap/intake/test_roadmap_intake_sub_issues.py` in the test function `test_a_part_is_never_a_duplicate_of_the_issue_its_source_names` from `body.endswith(f"Source: {source}")` to the form that `NewCandidate.filed_body` now writes: the body ends with the `## Source` heading and then the source. The test keeps its check that the part is filed and that its parent folds nothing
  - Verification: `$ uv run devops ci test tests/roadmap/intake/test_roadmap_intake_sub_issues.py` passes

## 4. State the blocker rule in the roadmap pages

Kind: other. Reads: `docs/roadmap/refine.md`, `docs/roadmap/stage.md`, `docs/roadmap/intake.md`, `src/devops_cli/roadmap/refine/refine.py`. Changes: `docs/roadmap/refine.md`, `docs/roadmap/stage.md`, `docs/roadmap/intake.md`.

- [x] 4.1 Rewrite the Dependencies paragraph of `docs/roadmap/refine.md` to state the blocker rule of task 5.1, with the forms that name a blocker and the links that name none, and keep the quoted-title rule. Rewrite the sentence of `docs/roadmap/stage.md` that names the Dependencies section to the same rule, and keep its pointer to `roadmap-stage/selection`. State in `docs/roadmap/intake.md` that intake writes the source under a `## Source` heading after the body
  - Verification: `$ uv run devops ci docs` passes
- [x] 4.2 Rewrite `docs/roadmap/refine.md`, `docs/roadmap/stage.md` and `docs/roadmap/intake.md` to state the blocker rule of task 5.1 and that intake files its source under its own heading
  - Verification: `$ uv run devops ci docs` passes

## 5. Fix the findings of the plan review

Kind: behavior. Reads: `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/intake/intake.py`, `src/devops_cli/roadmap/dependencies.py`, `src/devops_cli/config/constants.py`. Changes: `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/intake/intake.py`, `src/devops_cli/config/constants.py`, `tests/roadmap/refine/test_roadmap_refine_dependencies.py`, `tests/roadmap/test_roadmap_dependencies.py`, `tests/roadmap/intake/test_roadmap_intake_evidence.py`, `tests/roadmap/intake/test_roadmap_intake_sub_issues.py`, `tests/roadmap/intake/test_roadmap_intake_agent_candidates.py`.
Adds: `_sentences`, `_units`, `_sentence_blockers`, `_bare_word`, `NewCandidate.filed_bodies`

- [x] 5.1 Keep the prose blockers: each `#N` names a blocker, also in prose, except in a block that starts with `None` or `No`, after a link word of its sentence (`Part of`, `Child`, `Tracker`, `Related`, `Source`, an owner decision), in a sentence with a reverse phrase (`needs this item`, `this item blocks`, `is the parent`, `does not wait for`), in a block whose issue merges in either order, and in parentheses with other words. A sentence ends at `.`, `;`, `!`, `?` or a line end, outside parentheses. Write the failing tests first from short copies of the Dependencies sections of #4867, #5430, #4993, #4921, #5379, #5348, #4765, #4848, #5001 and #5026
  - Verification: `$ uv run devops ci test src/devops_cli/roadmap/refine/refine.py` passes
- [x] 5.2 Test `open_dependency`: `Related: #N` with #N open gives no reason, and `Depends on #N` with #N open gives the reason
  - Verification: `$ uv run devops ci test src/devops_cli/roadmap/dependencies.py` passes
- [x] 5.3 Write `Source: <source>` under the `## Source` heading, and let `_new_subject` find an issue of the old form
  - Verification: `$ uv run devops ci test src/devops_cli/roadmap/intake/intake.py` passes
- [x] 5.4 Set `CONST_ROADMAP_REFINE_RULES_SINCE` to the time of the fix, and state the full rule in the base specs and the roadmap pages
  - Verification: `$ uv run devops openspec check` passes
- [x] 5.5 Keep the blockers that a sentence opens with other words, drop the links that open with `#N`, and keep the hold issue of the freeze (#6521) and not the tracker in its note. The tests `test_body_dependencies_keeps_a_blocker_written_in_prose`, `test_body_dependencies_names_no_link_in_a_list_item_or_a_blocker_line` and `test_the_hold_line_names_its_hold_issue_and_not_the_tracker` of `tests/roadmap/refine/test_roadmap_refine_dependencies.py` fail on the second draft (12a2cd819) and pass after it, and `test_the_reason_of_a_held_item_names_the_hold_issue_and_no_link` of `tests/roadmap/test_roadmap_dependencies.py` passes. On the 806 open bodies of 2026-11-20, the rule adds no issue to what the base reads, each open issue that it drops is a link, and the 14 bodies with the hold line name #6521
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_dependencies.py tests/roadmap/test_roadmap_dependencies.py` passes

## Criteria

- Group 1: Test first: a Dependencies section that holds "None.", then "Source: #N", gives no dependency. The test fails on the base.
- Group 1: A test: "Part of #N", "Child 2 of #N", "Related: #N" and "#N needs this item" give no dependency. "- #N" and "Merge first: #N" still give one.
- Group 5: A blocker in prose ("#N (merged first).", "Depends on #N", "Open the pull request after the pull request of #N merges") still gives one, and the hold line "- #6521 (hold: ... of #6519)" gives #6521 only.
- Group 2: Intake writes the source line under its own heading, or as a link, so that it is never under Dependencies.
- Group 4: `docs/roadmap/refine.md` and `docs/roadmap/stage.md` state the rule.
- Pending person: Live proof: after the release, `devops roadmap explain 5001` and `devops roadmap explain 5026` give no dependency reason., Only a person can run the live check on the real roadmap after the release, because the plan changes no live item and the command reads the deployed Service.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
