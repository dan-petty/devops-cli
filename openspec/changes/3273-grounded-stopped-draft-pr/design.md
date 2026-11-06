# Design

## Decision

Put `Closes #{number}` in the draft body message. The draft is grounded from the first push.

## Rejected alternatives

- **Test the formatted body with `closing_keyword_in` and add a trailer when it holds none.** Rejected: the message is a constant of this repository. Read at `origin/main` 555280ff, it holds no keyword, and the test of the job now proves that the keyword is there. A runtime guard for a text that the code owns is dead code.
- **Reconcile the body on stop or on resume.** Rejected: the body stays ungrounded from the first push to the stop, and the job needs a read and a second write of the pull request. A Job that dies before its stop handler would still leave an ungrounded draft.
- **Excuse a draft in the grounding check.** Rejected: it weakens the gate for every draft and hides the missing keyword. `grounding.py` stays as it is.
- **Keep the draft ungrounded on purpose, so that a merge of a stopped draft closes nothing.** Rejected: the Status is Blocked and only a person merges. The readiness check already blocks a draft with an unarchived change, so the closing keyword adds no risk.
