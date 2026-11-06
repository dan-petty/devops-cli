# Design

## Decisions

- **A job failure has two next steps, `retry` and `failed`.**: The step is in the job record, so the selection and the inbox read one value and need no second rule for the limit. `retry` means that a later round tries again, and `_still_waiting` returns no wait for it. `failed` means that the try limit is reached, and only a body edit ends it, as for `edit`.
- **The limit is the constant `CONST_ROADMAP_REFINE_MAX_TRIES`, 3.**: Two retries cover a transient reply. A test patches the constant. The design of the issue says "configurable"; a setting adds a config key and generated documents for a number that nobody has asked to change, so the constant follows the other refine limits.
- **The tries count one body.**: The job record keeps `refine.tries` next to `refine.body_hash`. A round counts on the previous value only when the recorded body hash equals the hash of the body it read. A body edit starts at 1 again, and a proposal that passes clears the count.
- **A job failure writes no body and no comment.**: The failed reply is not a design, and a comment would use one of the two comments that a day allows (`CONST_ROADMAP_REFINE_MAX_COMMENTS_PER_ITEM`) for text that nobody can act on. The record is the report. The existing path for an item that is too big (`record_only`) already writes the hashes and the step and nothing else, so a job failure reuses it.
- **A job failure comes before every person wait.**: A proposal that fails a form check or holds an open question that a tool should answer is not valid. To ask a person on it wastes the time of that person. The question marked `(a person decides)` appears when the next round gives a valid proposal.
- **Only the mark `(a person decides)` makes a person wait among open questions.**: `validate_proposal` marks the question of a `person` kind and the unanswered `covers` question with it. Every other open question (`(missing verified source)` or no mark) is a question that a tool or the model should have answered.
- **A stopped investigation is a failure only while a question that is not a person's stays open.**: When the stop leaves only person questions and `(proposed)` decisions, the first proposal stands, as before.
- **The form checks are `problem_statement`, `existing_tool` and `acceptance_criteria`.**: `form_checks` returns the names, and `check_ready` is true only when the list is empty and nothing else blocks. A proposal that does not fit one pull request needs no acceptance criterion: a person splits it, so `acceptance_criteria` is a check only when `fits_one_pr` is true.
- **`InvestigationTools.searched` lists each call.**: Each tool appends its name and its argument. The failure text names at most the last `CONST_ROADMAP_REFINE_FAILURE_MAX_CHARS` characters of it. The text goes into the job record, where every `>` is escaped.
- **A Ready item that fails the form check keeps its Status.**: The failed reply is not written, so the earlier design stays in the body. The record shows the failure. This differs from a Ready item that refine finds not ready, which goes back to New with a comment, because that finding is about the item and the failure is about the reply.
- **The report counts the items that go on without a person.**: The count is the items of the plan, refined or waiting, whose next step is `ready`, `blocked` or `retry`. Each is listed. A `failed` item shows in the inbox, and `person`, `split` and `edit` need a person.

## Rejected alternatives

- **Keep the person wait and change its text.**: A person cannot act on a form check. The wait hides the job defect, as the 16 items show.
- **Fail the item at once, with one try.**: The model reply varies between rounds. A reply that fails once often passes in the next round, and the item loses nothing by the second look.
- **Retry with no limit.**: An item with a permanent defect would use model calls each round and never reach the inbox.
- **A new label or a new store for the failure.**: ADR 0001 keeps the job record in the issue body, and the labels hold only Status, Priority, Value and Effort.
- **Run the investigation more than once in a round.**: The tool budget is bounded for the window of the model. A later round is the retry, and it bounds the cost per round.
- **A setting for the limit.**: See the decision above.
