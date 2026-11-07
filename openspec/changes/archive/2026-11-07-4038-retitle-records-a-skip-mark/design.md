# Design

## Decisions

- **Hash the whole body of the item, as `Item.body` holds it.**: The issue says "the body". `Item.body` has the record block taken out, so the write of the mark does not change the hash. A rewrite of the refine section or of the alternatives block returns the item to the selection once. That costs one decision and keeps one rule that a reader can state.
- **Record a model failure as a skip.**: The model gave no title that passes the form in two tries. A third try on the same text costs 2 model calls and gives the same result in most cases. The item returns when the title, the body or `stage.pr` changes.
- **Record the mark for a person's edit too.**: The issue asks for it. The decision reads the comments and the title changes, and neither changes while the title and body stay the same.
- **Write the mark in `apply_retitle`, once for each `TitleSkip`, with `store.set_marks`.**: `apply_retitle` is the one write point of the job, and `plan_retitle` writes nothing. A `ModelGatewayUnreachableError` raises in the plan, before the apply step, so a gateway fault records no mark and the item stays in the selection.
- **Make `long_title_items` do the check.**: The selection is where the item holds a place of the limit. A check inside `_decide` would still count the item against the limit.
- **Use `StageRecordKey.PR` for the plan input.**: The plan pull request is the only source of a title for a Planned item, so its number is the one mark that the decision reads.
- **Add the key family before the failure-class issues of #3027.**: Those issues extend the job record, and this change gives them the union that they extend.

## Rejected alternatives

- **Hash `text_of_a_person(item.body)`.**: That text leaves out the refine section and the alternatives block, so a round of those jobs would not return the item. The model reads the first characters of the whole body (`_request`), so a change in a section can change the reply. The issue names "the body".
- **Keep the skips in memory for the run.**: The job runs every 61 minutes as a new process, so a memory set is empty at the next round. The mark must outlive the run.
- **A timestamp or a retry count in the mark.**: The issue asks for a hash of the inputs. A timestamp returns the item with no change of its inputs and costs the reads again.
- **Skip the mark for a plan pull request with no usable title.**: The reason changes only when the plan pull request or its title changes. The item already carries a comment for it. A mark ends the repeated reads.
