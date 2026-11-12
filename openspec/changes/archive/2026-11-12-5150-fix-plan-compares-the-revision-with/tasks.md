# Tasks

## 1. The review of the head counts the findings before the repair

Kind: behavior

- [x] 1.1 Write failing tests with the real stage comment of #4980: the revision is compared with a review of the head and not with the comment, the planner gets the findings of the comment and of the review, a clean review of the head clears the label though the comment lists a finding, a comment of an untrusted author gives the planner no finding, and the result line holds `comment`
  - Verification: `$ uv run devops ci test tests/roadmap/steps/test_roadmap_fix_plan_comment.py tests/roadmap/steps/test_roadmap_fix_plan.py`
- [x] 1.2 Review the head in each attempt of `_Planner.revise`, give the planner the findings of the review and of the comment, and add the count `comment` to the attempt, its result line and the report of the command
  - Verification: `$ uv run devops ci test tests/roadmap/steps/ tests/commands/test_roadmap_step_fix_plan.py`

## 2. Documents

Kind: other

- [x] 2.1 Update the fix-plan section of `docs/roadmap/stage.md` and the `fix_plan` row of `docs/roadmap/job-success.md`
  - Verification: `$ uv run devops ci --check --only docs,openspec`
- [x] 2.2 Regenerate the documents of the commands and the messages
  - Verification: `$ uv run devops docs generate --sync-readme`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
