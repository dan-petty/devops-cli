# Design

## Decisions

- **A criterion holds a name, a requirement, a scenario name, WHEN and THEN.** These are the parts of one OpenSpec requirement block with one scenario, so the rendered block goes into a spec delta as it is.
- **The SHALL or MUST rule is a schema rule.** A `requirement` without the keyword fails validation, so `chat_structured` sends the error back to the model and asks again, through the retry path that every structured call already has (#2452).
- **`existing_tool` is required, and an empty answer is not Ready.** The feature request form requires the field, and a required key is in the JSON schema that a constrained provider enforces (#2550).
- **The rendered section keeps its `### Acceptance criteria` heading** and puts the requirement blocks after it, so the section's headings stay the same for a person who reads the issue.

## Rejected alternatives

- **Only `{requirement, when, then}`, as the issue words it.** OpenSpec 1.14.3 requires a name after `### Requirement:` and after `#### Scenario:`, and a SHALL or MUST in the requirement's body, not in its header (`requirement-blocks.js`, `requirement-text.js`, `validator.js`). With three keys the renderer would have to make up the names, and the block would not pass `openspec validate --strict`.
- **Derive the names from the requirement text.** No rule gives a short name from a sentence, and a truncated sentence is not a name.
- **Check SHALL or MUST in `check_ready`.** A proposal that fails `check_ready` waits on a person with a next-step comment. A schema error goes back to the model in the same call, at no cost to a person.
- **A default empty `existing_tool`.** The model could leave the key out, and the item would then wait on a person. A required key makes the schema and the retry ask for it.
- **Change the builder and reviewer briefs.** No such file exists in the repository.
