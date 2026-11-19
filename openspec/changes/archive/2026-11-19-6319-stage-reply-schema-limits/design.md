# Design

## Decisions

- The schema of `pull_request_body` holds no `max_length` and no `maxLength` hint. A provider that constrains the reply to the JSON schema can cut a string at `maxLength`, and a cut text drops plan text.
- The stage job measures the text of the body as `safe_text` writes it, against the room that `pull_form.plan_body_room` gives for the issue number and the change folder. One helper of `pull_form` builds the `Plans` and `Change:` lines for the room and for `build_plan_body`, so the two counts cannot differ.
- Only a text over its room gets the rewrite turn. A body that the plan form refuses for another reason (a short text, a placeholder, attribution lines) goes back to the planner, as before: the planner has the context to write a new text, and the rewrite has only the old text.
- The rewrite turn is one `chat_structured` call with `BodyReply`, the prompt `roadmap_implement_body.md` and one problem that gives the length and the room. A reply that breaks the `BodyReply` schema goes back once, as each structured call of the stage does, and the job does not catch the error.
- The proposal keeps the full text of the model. The draft body holds the shorter text. The kept plan file keeps the proposal, so a rerun reads the full text.
- `OptionalLine` is `Line` with a `BeforeValidator` that maps `None` to the empty text. `security` of the proposal and `kind` of a reference take it. The JSON schema of the field stays `string`, so the model sees no change.

## Rejected alternatives

- Keep the cap and give more returns: #4012 failed after 4 returns, and the owner rule of 2026-11-17 forbids a hard character cap that fails a job.
- Send a long body back to the planner through the body gate: each return plans the whole item again with tools; one run of #6319 used about 16.8 M tokens in 79 minutes.
- Cut the text at a sentence end: a single long sentence has no such end, and `pull_form` refuses a cut text by rule.
- Give the body limit as a `maxLength` hint in the JSON schema: a provider that constrains the reply to the schema cuts the text at that length.
- `security: str | None = None`: the writer and the checks read `security` as a string, so `None` would reach the change files.
- A new prompt for the stage rewrite: `roadmap_implement_body.md` already asks for a text that fixes each problem and keeps the facts.
