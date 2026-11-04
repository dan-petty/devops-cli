# Design

## Decisions

- **The renderer decides the tuicr bullet from the paths of the groups.**: openspec/config.yaml allows the bullet only for a change that alters code, and a plan for a documents-only change has no code diff to review.
- **The renderer writes the Workflow follow-up section only when it holds a bullet.**: An empty heading is text that the plan does not need, and the bullet is the only content the section carries.
- **The docs regeneration step follows the paths in the commands package and the lang package.**: Only a change of a command, an option or a message changes the generated documentation, so a documents-only group adds nothing to it.
- **The renderer prepends the fixed verb Edit when the first word of the documentation text is a path.**: A root document such as SECURITY.md holds no slash, so a test on a slash alone leaves it without a verb.
- **The renderer keeps a documentation text whose first word is a verb.**: A second verb gives Edit Document, which breaks the task grammar and the rule of AGENTS.md.
- **The stage prompt states the documentation rule and the renderer keeps its own check.**: A prompt guides the model and cannot guarantee that a rendered task starts with a verb.
- **The plan reader derives its document mark from the document-work template.**: The reader separates the document work from the rest of the task, and the template splits into the document work and the regeneration suffix.
- **The plan carries no documentation task.**: The change edits an internal task template and a stage prompt, and no committed document describes them. The implement job runs the docs generation with its checks and commits any file that it changes.

## Rejected alternatives

- **Validate the model's documentation text for an English verb.**: The context shows that the model writes the field and that the prompt already asks for a document, so a natural-language check stays fragile and accepts a bad sentence, while the fixed Edit verb is deterministic.
- **Prepend Edit to every documentation text.**: The text Document the fix in docs/TESTING.md at tests/roadmap/test_roadmap_stage_plan.py:726 would render as Edit Document, which breaks the task grammar.
- **Test the first word for a slash only.**: SECURITY.md is a file of the staging commit and holds no slash, so the test would leave it without a verb.
- **Rely on the prompt alone.**: openspec/config.yaml shows the prompt as guidance, and the rendered tasks.md is what the plan check and the task grammar read, so a prompt cannot hold the rule.
- **Add the docs regeneration step to every group that names a document.**: A group that changes only SECURITY.md changes no command, an option or a message, so the step regenerates documentation that the change does not touch.
- **Add the tuicr review bullet to every plan.**: openspec/config.yaml allows the bullet only for a change that alters code, and a plan for a documents-only change alters no code.
