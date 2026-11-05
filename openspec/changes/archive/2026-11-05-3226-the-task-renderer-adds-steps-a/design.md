# Design

## Decisions

- **The renderer decides the tuicr bullet from the paths of the groups.** openspec/config.yaml allows the bullet for a change that alters code. A plan that changes no path under `src/` has no code to review in tuicr.
- **The renderer writes the Workflow follow-up heading only when it holds a bullet.** An empty heading is text that the plan does not need.
- **The regeneration step follows the paths under `src/devops_cli/commands/` and `src/devops_cli/lang/`.** A change to a command, an option or a message changes the generated documentation. A documents-only group changes none of it.
- **The renderer prepends the fixed verb `Edit` when the first word of a documentation text is a path.** A path is a word that holds `/` or ends in a dot and letters. A root document such as `SECURITY.md` holds no slash, so a test on the slash alone would leave it with no verb. The renderer writes the path in a code span, as the planning rules require.
- **The renderer keeps a documentation text whose first word is not a path.** A text that starts with a verb, such as `Document the fix in `docs/TESTING.md``, stays as written.
- **The stage prompt states the documentation rule, and the renderer keeps its own rule.** A prompt guides the model. It cannot guarantee that a rendered task starts with a verb.
- **The plan reader derives its document mark from the regeneration template.** The mark is the suffix `, and run `uv run devops docs generate --sync-readme``. A documents-only task has no mark, so the reader returns its whole text, and the verb stays in the work.
- **The planning rules in openspec/config.yaml state the same two rules.** AGENTS.md rule 8 requires a document that a change makes wrong to change in the same pull request.

## Rejected alternatives

- **Validate the documentation text of the model for an English verb.** A natural-language check is fragile and accepts a bad sentence. The fixed verb `Edit` is deterministic.
- **Prepend `Edit` to every documentation text.** The text `Document the fix in `docs/TESTING.md`` at `tests/roadmap/test_roadmap_stage_plan.py` would render as `Edit Document`, which breaks the task grammar.
- **Test the first word for a slash only.** `SECURITY.md` is a file of the repository and holds no slash. The test would leave it with no verb.
- **Rely on the prompt alone.** A prompt cannot hold the rule, because the rendered `tasks.md` is what the plan check and the task grammar read.
- **Add the regeneration step to every group that names a document.** A group that changes only `SECURITY.md` changes no command, option or message. The step would regenerate documentation that the change does not touch.
- **Add the tuicr review bullet to every plan.** openspec/config.yaml allows the bullet only for a change that alters code, and a documents-only plan alters no code.
- **Strip the verb in the plan reader.** The reader would have to guess which words are the verb. The task keeps the verb, so the reader returns the task as written.
