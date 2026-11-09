# Design

## Decisions

- **The schema accepts null and the prompt keeps "else null".** The schema that pydantic-ai sends then says `string` or `null`, so the model reads the same rule in the prompt and in the schema, and a reply of either `null` or an empty string passes. The reason is that acceptance criterion 1 of #4214 asks for a null reason to validate, and that the prompt stays right.
- **The design file reads a null reason as an empty string.** The one use site of `ref.reason` is `render_change`, which writes only unchanged references. The validator refuses an unchanged reference with a null or blank reason, so the read cannot meet null there; the read is written as `(ref.reason or "")` for the type checker.
- **The prompt rule test reads the prompt.** The test takes the words after `else` in the sentence about `reason` in the `references` key (`null` or `an empty string`), builds a reply with that value, and validates it with `StageProposal`. A later edit of the prompt or of the schema that disagrees with the other fails the test.

## Rejected alternatives

- **The prompt says "else an empty string" and the schema stays.** Rejected: acceptance criterion 1 of #4214 asks that a null reason validates, and a model reply of null after this change would still fail. It also leaves a schema that is stricter than the prompt of other keys that use null (`purpose`).
