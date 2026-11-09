# Design

## Decisions

- **Mask and cut where the text is made.** `ViolationText` masks and cuts its fields in a pydantic validator. Each use (the failure line, the log line, the refused file) then holds only safe text, and a later use needs no second step. Mask comes before the cut, so a cut cannot leave the start of a secret.
- **The trace keeps 3 texts and the count.** The count of the retry prompt stays the truth for "how many". The texts are the first 3 only, so a trace stays small.
- **The error carries typed fields.** `violation_texts` and `stop_reason` of `StructuredOutputValidationError` are read by the stage; the message of the error stays free of model text, as its other callers expect.
- **The stop reason is `validation` when the retry prompt held errors, else `no tool call`.** `InvestigationStopped.schema_broken` already means the last reply held no call to a tool of the run. The errors tell the two cases apart. A reply of plain text is a `validation` stop with the type `json_invalid`.
- **One record, one more field.** The schema failure goes in `schema_failure` of `<n>.refused.json`, with the replies that the checks refused before it. A schema failure has no reply to keep, so it is not a `RefusedReply`. The staging of the item deletes the same file as before.
- **The catch is in `_gated`.** Only a plan ask has the key and the refused replies. The ask of a repair round keeps the failure line only.

## Rejected alternatives

- **Put the text in the message of the error.** Rejected: the message reaches spans and other logs, and its other callers rely on that it holds no model text.
- **Fill the text in the plain `chat_structured` client too.** Rejected for this change: its message was made free of field paths on purpose, because a path can be a key that the model invented. The stage job uses the toolbox client.
