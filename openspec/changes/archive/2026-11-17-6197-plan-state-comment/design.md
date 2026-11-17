# Design

## Decisions

- The state comment keeps the marker of the stage job and adds a hidden key line `<!-- devops roadmap plan state #<pull> -->`. So every reader of a stage comment, such as the repeat guard, the replies check of refine and repair, and the person check of the comment index, reads it as a comment of the stage job. The key names the pull request, so a new pull request gets a new state comment, and the state comment of an older pull request stays as history.
- The upsert is `steps/comment.py` `post` with a `Target` of the store whose listing holds only the comments of a trusted author: a comment of another account that copies the key is never edited and never read as the state.
- The store gets `edit_comment`. The store path of `Target` called the private `_roadmap` of the fake or `_write` of the GitHub store, which made product code detect the test double. A comment with no id cannot be edited, so the path raises in place of a write that does nothing.
- The comment of a run holds a hidden event line, so the legacy read of `plan_comment` skips it by its line and not by its text: a comment of a run that keeps no finding must not hide the findings of the legacy comment before it.
- The step re-renders the groups from the pushed plan after a push, since the groups of the plan changed. With no push it keeps the groups section of the state comment as it stands, or that of the newest legacy stage comment.
- The comment of an attempt keeps its advice section, as #6197 asks: it is the history of the attempt, and the state comment holds the advice of the current plan.
- `held_comments` orders only a state comment by its last edit. Another edited comment, such as a correction of a person, keeps the place of its creation, as the readers of replies expect.

## Rejected alternatives

- A new marker for the state comment: each reader of a stage comment would need the new marker, and the repeat guard and the comment index would read it as no comment of a job.
- The state comment in the body of the issue: the record block and refine own the body, and each write of the body races the writes of the record.
- Find the event comments by their text: a legacy comment of fix-plan with no open finding (`cleared`) and a comment of a run look alike, and a wrong guess drops the open findings of the legacy comment.
- Order every edited comment by its last edit: a person who fixes a typo in an old decision would move it after the later decisions.
