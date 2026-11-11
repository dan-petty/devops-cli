# Tasks

## 1. Parse only the bodies that hold a record block
kind: other

- [x] 1.1 In `src/devops_cli/roadmap/stores/store.py`, return the body and an empty record from `split_record` with no parse when the body does not hold `_RECORD_OPENER`, and turn off the core rule `inline` of `_BODY_MARKDOWN`. The contract tests of the record block (#2538) keep the behavior.
  - Verification: `$ uv run devops ci test tests/roadmap/stores/ tests/roadmap/intake/ tests/roadmap/refine/test_roadmap_refine_sanitize.py`
- [x] 1.2 Show that the result is the same and the parse is faster on the real listing.
  - Verification: read the bodies of the listing once through `GitHubRoadmapStore("dan-petty/devops-cli").issues()`, with a wrapper of `split_record` that keeps each body. Run `split_record` over all of them in a checkout of `origin/main` and in this branch, and keep the JSON of the results and the CPU time (`time.process_time`). The two JSON files are the same, and the CPU time of this branch is less than one third of the base.

## Workflow follow-up

- #4404 files the other cuts of the intake call as their own items: the GitHub read of the listing, the embeddings, and the writes.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
