# Tasks

## 1. A refusal of the review is a job failure (behavior)

- [x] 1.1 Write failing tests: a refusal records the step `retry`, the check `judge_refused` and the findings, and writes no comment; the next round gives the findings to the model and an approval sets the item Ready; the third refusal gives `failed` and the inbox lists the item; a body edit after the third refusal starts the count again; a refused Ready item goes back to New with the step `retry`
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_trust.py`
- [x] 1.2 Route the refusal to a job failure in `refine_one_item`, record `refine.judge_findings`, add `judge_findings` to the request and the two refine prompts, register the new limit, and delete the `edit` comment text
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_trust.py tests/roadmap/test_roadmap_limit_classes.py`
- [x] 1.3 Regenerate the documentation for the changed messages
  - Verification: `$ uv run devops docs generate --sync-readme`

## 2. Documents

- [x] 2.1 State the new route of a refusal in `docs/roadmap/refine.md`, and the new record key in `docs/ROADMAP_WORKFLOW.md`
  - Verification: `$ uv run devops ci docs`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
