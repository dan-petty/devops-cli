# Design

## Decisions
- **Retitle owns the correction.** The retitle row runs before the stage row of each round and already writes titles with a comment and a skip mark. The correction of an existing Ready item belongs there, so the three waiting items move in the next round.
- **One correction table, beside its owner.** `_TITLE_TYPE_CORRECTIONS` in `commit_title.py` maps `security` to `fix(security)`. Only that module reads it, so it is not in `config/constants.py` (`CONTRIBUTING.md`, Closed Lists). The scope becomes `security` because the urgent-fix rule of intake reads `scope/security` (#2768). The table has one entry, the one type that the data shows. Another unlisted type gets one comment that names the types, and a person corrects it: the job does not guess a type.
- **The correction does not wait for the model.** A short summary needs no model call. A long summary gets the usual model or plan pass on the corrected title. When that pass fails, the job still writes the corrected type with the old summary. The stage job then gives the "long title" reason, and the next round selects the item as any long title.
- **A person's edit stays.** The rule of #3486 holds. When the kept title has an unlisted type, the skip comments once, so the person learns why the stage job cannot take it.
- **Refine does not set Ready an item with an unlisted type.** The selection of refine reads the title before any other read and leaves the item with no model call, also with `--item`. It records no step, so nothing ends a wait: the first round after a title with a listed type refines the item. A type with a correction waits on nothing that refine does (`NONE`), because the retitle row of the same round corrects it. Another type waits on a person.
- **Intake keeps the candidate.** As #4508 chose, intake keeps the early return of its summary check: retitle corrects the type of the new item, and refine holds it New until then.
- **The stage reason names only what retitle does.** `unlisted_type_reason` builds the reason from the correction table: the corrected title, or the comment of the retitle job for a type with no correction. A title with no type, such as `The board is slow`, keeps the old reason, because the retitle job does not select it.
- **One log line for each skip.** `apply_retitle` logs each skip with a reason key. The skip mark keeps the item out of the next rounds, so the line comes once for each title, body and plan state.

## Rejected alternatives
- **Add `security` to `CONST_BRANCH_TYPES`.** `tests/git/test_branch_form.py` holds the list equal to the `changelog-sections` of `release-please-config.json`, and `CONTRIBUTING.md` names the same eleven types. A new section changes the changelog, the `Semantic PR title` check and the branch hook for one label.
- **Refine refuses Ready after a model call.** The refine round would pay for a proposal that it cannot use, and a recorded wait ends only on a reply or a body edit, not on a title change. The check in the selection costs nothing and ends with the title.
- **A refine comment on the refusal.** The retitle row of the same round writes one comment with the type, the types and the correction. A second comment from refine names the same cause again.
- **Intake refuses an unlisted type.** It blocks a candidate that retitle can correct (#4508, key question on intake).
- **A stage log line and a metric label for each left-out item in this change.** #4521 added both for every left-out rule (PR #4541), with the kind `title_type`.
- **Guess a type from the `type/*` label.** `type/infra` maps to perf, build and ci, so the guess is not deterministic for every label.
