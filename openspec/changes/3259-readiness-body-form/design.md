# Design

## Decisions

- **Add the blocker kind `BODY_FORM`.** Each command maps a kind to its exit code, so a body problem gets its own name. `check-readiness` exits 1 on any blocker, `pr monitor` exits 2 for a kind that is not a check failure, and `pr ready` warns.
- **Call `body_problems` from the item rules.** `_judge_grounding` already returns early where the base holds no `openspec/changes/`, and that is where the form of the body applies too (the form names a change folder). A plan pull request returns before the call, because `plan_blockers` judges its body.
- **One blocker for each problem, with the pull request number in front.** The text of a problem from `body_problems` does not name the pull request. The new message `body_form_problem` adds `PR #<number> body:` so that a line in the monitor output still names its pull request.
- **Delete the length warning.** `body_problems` limits the body to the same 1,000 characters. Keeping `_judge_body_length` would report the same fault as a warning and as a blocker, and its requirement says that the body warning blocks nothing.

## Rejected alternatives

- **Print the problems from the command and leave the verdict alone.** Then `pr monitor` and `pr ready` would not see them, and the verdict would no longer be the one place that judges a pull request. The verdict is the shared function by design.
- **Warn only.** A warning lets a pull request pass readiness with a broken body, and the issue asks for a non-zero exit.
- **Report the first problem only.** It hides later problems and needs one run for each fix.
- **Keep the warning beside the blocker.** It repeats the rule of `body_problems` and contradicts the removed requirement that it blocks nothing.
