# Design

## Decisions
- Remove `"drop"`, `"drops"`, `"dropped"`, and `"dropping"` from `REMOVAL_VERBS` in `src/devops_cli/roadmap/stage/stage_removal_references.py`. Keep `"remove"`, `"delete"`, `"deprecate"`, and `"retire"` (plus their inflections) in active and passive forms.
- Update `test_find_removed_names_handles_multiple_identifiers_and_verbs` to expect `"tool_a"` not to be returned from `"Another item drops \`tool_a\` from \`registry\`."`, add tests for active/passive `drop` forms and `deletes` findings, and add a `removes` keyword test so Python keyword skipping remains directly verified on an active removal verb.

## Rejected alternatives
- **Filter `drop` only when followed by nouns like `step`**: plans frequently omit the noun (`dropped \`rewrite\``) or place another word in between, leaving false positives behind.
- **Keep `drops` while excluding `dropped`**: `drops` is also commonly used in prose (`drops the retry`), so excluding the whole `drop` inflection family matches all other verbs in `REMOVAL_VERBS`.
- **Also remove `deprecate` or `retire`**: those verbs consistently denote removing a code entity, whereas only `drop` conflicts with step and behavior wording.
