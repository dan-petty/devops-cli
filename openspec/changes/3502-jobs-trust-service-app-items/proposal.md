# Proposal

## Why

Issue #3502: the roadmap jobs treat an item of the Service App or of `github-actions[bot]` as text from an outsider. GitHub gives both bots the association CONTRIBUTOR, and `CONST_ROADMAP_TRUSTED_AUTHORS` holds only OWNER, MEMBER and COLLABORATOR. So refine, the stage job, the implement job and the alternatives job leave the item out. Refine writes no comment for it, so a part that refine split off itself waits with no signal. On 2026-11-05, 38 of 154 New items waited on this rule: 27 from the Service App, all `Split from #N`, and 11 from `github-actions[bot]`, all hardening titles.

The repository is public, and refine gives the replies of any account to the model. The model writes the split-offs. So the change must not let text from an outside reply reach a Ready item with no person. The owner decided on 2026-11-05 that bot-filed work proceeds with no person, when an agentic judge approves the issue and the proposal of refine.

## What Changes

- `Item`, `IssueRecord` and `IssueComment` hold the author login. The GitHub store reads it from `user.login`.
- A new module, `src/devops_cli/roadmap/trust.py`, holds the one trust rule. A job takes an item whose author has write access (OWNER, MEMBER or COLLABORATOR), or whose author login is exactly `service.github_app.bot_login` or `github-actions[bot]`. A login that only resembles one of them is not trusted. With no App slug set, no item of the App is trusted.
- The four readers (refine, stage, implement and alternatives) use that rule. `retry_asked` in `implement.py` does not change, so a bot gains no retry right. `intake.py` does not change.
- Refine reviews a Ready proposal for an item of a bot. The review is the verification pass of the stage job (`stage_verify.verify`, task slot `ai.tasks.verification`) in the new module `refine_judge.py`. An approval is recorded as `refine.judge` `approved`. A refusal keeps the item New with the step `edit`, and one comment lists each open finding with its evidence. A round that looks again at an approved item with an unchanged body makes no model call. An item of a person gets no review.
- The stage job, the implement job and the alternatives job take an item of a bot only with `refine.judge` `approved`.
- Refine tells the author of an item that the jobs do not trust, one time, why a round leaves it alone. The comment holds the marker `CONST_ROADMAP_REFINE_OUTSIDE_MARKER`, so a later round writes no second one.
- The model of refine reads only the replies of trusted authors: a person with write access, or the App's bot. This is the filter that protects the Ready path, because the review is a model and is no security control.
- `SECURITY.md` states the rule and its reason. `docs/roadmap/refine.md` and `docs/ROADMAP_WORKFLOW.md` describe the review and the record key.
- The detail lines and the comments are observable, so the change carries a spec delta: a new capability `roadmap-author-trust`, and a change to `roadmap-refine`.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `roadmap-author-trust`: which authors the roadmap jobs trust, the approval that an item of a bot needs, and the replies that the model of refine reads.

### Modified Capabilities

- `roadmap-refine`: MODIFIED for the items that a round takes, and ADDED for the review of an item of a bot and for the comment to the author of an item that the jobs do not trust.

## Impact

- Code: `src/devops_cli/roadmap/trust.py` and `refine_judge.py` (new), `store.py`, `github_store.py`, `memory_store.py`, `refine.py`, `stage.py`, `implement.py`, `alternatives.py`, `stage_verify.py` (`finding_line` becomes public), `config/constants.py` and `lang/en/messages.py`.
- Tests: `tests/roadmap/test_roadmap_trust.py` and `test_roadmap_refine_trust.py` (new), `test_roadmap_store_contract.py`, `test_roadmap_github_store.py`, `test_roadmap_implement_selection.py`, `test_roadmap_refine.py`, and the fakes `tests/roadmap_github_fake.py` and `tests/support/roadmap_implement.py`.
- Cost: one comment read for each item that the jobs do not trust, in each round, to find the comment that was written before. After this change, the Service App and `github-actions[bot]` items no longer count in that set. A round that refines a Ready proposal for an item of a bot makes one more model call, with the `verification` slot, and none for the item of a person or for an approved item with an unchanged body.
- The review sees the issue and the proposal, and no cited file, because `cited_files` reads only the `reads` and `changes` of plan groups, which a proposal does not have.
- The owner decides at merge: the change widens the trust rule of #2478 to two bots, and AGENTS.md rule 5 reserves that decision to the owner. The owner recorded the decision on #3502 on 2026-11-05.
- The alternatives job still sends all comments of an item to its model. That path is not in this change.

## Feasibility

- GitHub REST, read on 2026-11-05 with `devops gh api`: issue #3162 has `user.login` `devops-cli-service[bot]`, `user.type` `Bot` and `author_association` `CONTRIBUTOR`. Issue #3138 has `user.login` `github-actions[bot]`, type `Bot` and association `CONTRIBUTOR`. The comment of the App on #3502 has the same login and association. `users/github-actions[bot]` and `users/devops-cli-service[bot]` have type `Bot`. So the association cannot tell a trusted bot from another bot, and the login can.
- On the base `66a8a63e`, `_IssuePayload` and `_CommentPayload` in `github_store.py` read no `user`, and `Item`, `IssueRecord` and `IssueComment` held no login. `CONST_ROADMAP_TRUSTED_AUTHORS` was read in `refine.py`, `stage.py`, `alternatives.py`, `implement.py` (twice) and `intake.py`. `refine.py` `_replies_for_model` and `covers_question` gave every comment to the model.
- `GitHubAppConfig.bot_login` (`config/settings.py`) gives `<slug>[bot]`, or None with no slug. The cluster ConfigMap template sets `service.github_app.slug` to `devops-cli-service`.
- `stage_verify.verify` takes a `VerificationInput` whose `plan` is any mapping, so it reads a `RefinementProposal.model_dump()`. `stage.py` already builds its `StageClient` with `get_llm_client(task="verification")` in `run.py`. `open_findings` keeps a finding of an open type, or a placeholder, that quotes a text of the input.
- An import of `stage_verify` from `refine.py` fails on the first import: `stage_verify` imports `stage_change`, and `stage_change` imports `sanitize_text` from `refine`. So `refine.py` imports `refine_judge` inside the function that calls it, as `dry_run_refine` imports `request_plan`.
- The new tests fail on the base for the reasons that the issue names: no login field, no trust of the bots, no review, no comment, and the unfiltered replies.

## Existing Tool Considered

The code of the project covers the need, so nothing new is built. `GitHubAppConfig.bot_login` gives the exact login. GitHub's `user.login` gives the author. The verification pass of the stage job (`stage_verify.verify` with the slot `ai.tasks.verification`) is the review, as the owner decided. The job record (`RefineRecordKey`) holds the verdict, and `step_comment` and the `NextStep.EDIT` wait show a refusal. The change deletes no internal code, and it adds no setting and no model.
