# Design

## Decisions

- **A refusal is a job failure.** The check is `judge_refused`. It shares `refine.tries` and the limit of 3 tries on the same body with the other job failures (#3632). A form check failure and a refusal on the same body both count, because each one is a round that did not give a Ready proposal.
- **The refusal still writes the body and the Status.** The requirement "A round reviews a Ready item of a bot again when its approval ends" sets a refused Ready item back to New. The section of the refused proposal stays in the body, so the next request shows the model the proposal that the findings name.
- **The findings have their own key.** `refine.failure` holds at most 300 characters and the inbox prints it on one line. One finding with its quote is often longer. `refine.judge_findings` keeps each finding on its line, at most 2,000 characters, and `refine.failure` keeps the first finding for the inbox and `devops roadmap explain`.
- **The findings stay until a round does not fail.** A form check failure after a refusal keeps them, so the next request still has them. A body edit starts the count of tries again but keeps the findings, because they can still apply to the new body.
- **No comment.** A job failure writes no comment. The inbox lists the item at the limit, with the check, the count and the first finding.

## Rejected alternatives

- **A comment for each refusal, with no request to a person.** Three refusals give three comments. The cap of 2 refine comments in 24 hours (`CONST_ROADMAP_REFINE_MAX_COMMENTS_PER_ITEM`) would hold the third try for a day. The job record and the inbox give the same facts.
- **Read the findings from the last comment of refine.** The comment is text for a person, and a parse of it breaks when the text changes. The job record is structured.
- **Read an old record with the step `edit` and `refine.judge` `refused` as `retry`.** That is a shim for old data, and AGENTS.md forbids a shim. One `devops roadmap refine --item <number> --confirm` round for each of the 28 items puts it on the new route.
- **Write only the record, as the other job failures do.** A refused Ready item would then stay Ready with no approval that holds, and the requirement says that it goes back to New.
