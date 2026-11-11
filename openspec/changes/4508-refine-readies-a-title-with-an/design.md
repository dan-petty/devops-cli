# Design

## Decisions
- **Retitle owns the correction.** The retitle row runs before the stage row of each round and already writes titles with a comment and a skip mark. The correction of an existing Ready item belongs there, so the three waiting items move in the next round.
- **One correction table.** `CONST_ROADMAP_TITLE_TYPE_CORRECTIONS` maps `security` to `fix(security)`. The scope becomes `security` because the urgent-fix rule of intake reads `scope/security` (#2768). The table has one entry, the one type that the data shows. Another unlisted type gets one comment that names the types, and a person corrects it: the job does not guess a type.
- **The correction does not wait for the model.** A short summary needs no model call. A long summary gets the usual model or plan pass on the corrected title. When that pass fails, the job still writes the corrected type with the old summary. The stage job then gives the "long title" reason, and the next round selects the item as any long title.
- **A person's edit stays.** The rule of #3486 holds. When the kept title has an unlisted type, the skip comments once, so the person learns why the stage job cannot take it.
- **Intake refuses a new candidate.** As for a long summary (#3486), intake refuses a new candidate with an unlisted type before it is an issue. An existing issue with such a title goes through intake and refine as now, and retitle corrects it.
- **One log line for each skip.** `apply_retitle` logs each skip with a reason key. The skip mark keeps the item out of the next rounds, so the line comes once for each title, body and plan state.

## Rejected alternatives
- **Add `security` to `CONST_BRANCH_TYPES`.** `tests/test_branch_form.py` holds the list equal to the `changelog-sections` of `release-please-config.json`, and `CONTRIBUTING.md` names the same eleven types. A new section changes the changelog, the `Semantic PR title` check and the branch hook for one label.
- **Refine refuses Ready.** Refine is a model job, and an item that is Ready already does not go through refine again, so the three waiting items would stay. Retitle corrects the title, which removes the cause.
- **A stage log line for each left-out item.** The stage row runs about every 40 minutes, and it leaves out every open item that is not Ready. A line for each would repeat each round. The retitle comment, its skip mark and its one log line name the cause once, and `devops roadmap explain` shows the stage reason.
- **A reason label on the stage metric.** It changes the metric schema and the dashboards for one diagnostic.
- **Guess a type from the `type/*` label.** `type/infra` maps to perf, build and ci, so the guess is not deterministic for every label.
