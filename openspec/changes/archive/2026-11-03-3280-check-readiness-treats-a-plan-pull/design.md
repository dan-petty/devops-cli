# Design

## Decisions

- **Detect a plan by its title, `docs(openspec): plan #<issue> `, and not by its changed paths.**: `staging_title` writes this form for every plan, and a path test would take a delivery that only edits a change folder for a plan.
- **Put the plan rules in `src/devops_cli/roadmap/grounding.py`, as pure predicates over the title, the body and the changed files.**: The module already holds the delivery rules as pure functions, and `merge_readiness.py` only reads the facts.
- **Reuse `closing_keyword_in` of `src/devops_cli/roadmap/stage_change.py` for the keyword rule.**: The stage job refuses the same keyword when it writes the body, so one function states the rule.
- **Send no closing-issues request for a plan.**: A plan closes no issue, so the read has no use and the verdict stays correct when GitHub is slow.

## Rejected alternatives

- **Delegate the plan rules to `devops roadmap plan-check` (#3201).**: #3201 plans a command that reads the content of a change folder with a checkout, and readiness reads only the REST payload and the file list.
- **Detect a plan by the changed paths.**: `CONST_OPENSPEC_CHANGE_FOLDER_RE` also matches a delivery that archives a change, so a path test needs a second rule to tell them apart, and the title already tells them apart.
- **Skip all grounding for a plan.**: A plan with `Closes #<issue>` would close its issue when it merges, and a plan that writes `openspec/specs/` would bypass the archive.
