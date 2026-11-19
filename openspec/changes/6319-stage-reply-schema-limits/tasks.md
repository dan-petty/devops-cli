# Tasks

## 1. A long plan body gets a shorter text from one model turn

- [x] 1.1 Add failing tests: a reply with a 1200-character body is staged with the shorter text of one `BodyReply` turn and the proposal keeps the full text; a body in its room gets no rewrite; a shorter text over the room goes back to the planner; `plan_body_room` gives the room that `build_plan_body` measures; a body of the length that the prompt asks for fits the room with the longest number and slug
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_plan.py tests/roadmap/stage/test_roadmap_stage_prompt_rules.py tests/roadmap/test_roadmap_pull_form.py`
- [x] 1.2 Remove the schema cap and the stage constant `BODY_MAX_CHARS`, add `plan_body_room` to `pull_form.py`, make `BODY_TASK` of `pull_retry.py` public, and ask the model once for a shorter text in `Stage._plan_body` when the text is over its room
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_plan.py tests/roadmap/stage/test_roadmap_stage_prompt_rules.py tests/roadmap/stage/test_roadmap_stage_plan_check.py tests/roadmap/test_roadmap_pull_form.py tests/roadmap/test_roadmap_pull_retry.py`

## 2. A null optional text reads as its default

- [x] 2.1 Add failing tests: a reply with `security: null` is staged with an empty `security`, a reference with `kind: null` reads as an empty `kind`, and a reply with `security: 123` goes back to the model once with the field name
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_plan.py`
- [x] 2.2 Add `OptionalLine`, a `Line` with a `BeforeValidator` that maps `None` to the empty text, and give it to `security` of `StageProposal` and `kind` of `StageReference`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_plan.py`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
