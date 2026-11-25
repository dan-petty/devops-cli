# Design

## Decisions
- Use a deterministic text predicate `_is_post_merge_person_question(question)` in `src/devops_cli/roadmap/refine/refine.py` inside `validate_proposal`:
  - Matches a merge-act question asking `who` or `when` merges (or approves/accepts and merges) naming `pull request`, `pr`, `record`, `adr`, `change`, or `draft`.
  - Matches a post-release check question asking `who` runs, confirms, proves, verifies, or checks a `live proof`, `live keys`, `live check`, `proof`, or `check` after the merge or release.
  - Excludes pre-build questions naming `secret`, `repository setting`, or `host` (for example, `"Which repository setting enables the merge?"`).
- Convert matched `person` questions into one deduplicated `AcceptanceCriterion` with `name="Pending a person after the merge"`, omit them from `open_questions` and `validated_qa`, and keep `qa.body_question` in `named`.
- Bump `CONST_ROADMAP_REFINE_RULES_SINCE` to `2026-11-25T09:05:00Z` and keep the `Pending a person after the merge` prompt note outside the `person`-kind definition sentence in `roadmap_refine_reply.md`.

## Rejected alternatives
- Relying on a new `after_merge` boolean field or prompt edits alone: models can still emit `kind="person"` for merge or post-release check questions, so deterministic validation is required.
- Dropping every `person` question: pre-build `person` decisions on secrets, repository settings, and hosts still change the plan and must hold the item.
- Leaving post-merge checks out completely: owner decision `#4780` preserves them as `Pending a person after the merge` criteria rather than losing them.
