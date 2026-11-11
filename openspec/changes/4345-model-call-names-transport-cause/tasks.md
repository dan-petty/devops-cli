# Tasks

## 1. A failed transport names its phase and its error

Kind: behavior.

- [x] 1.1 Write failing tests: a dropped stream, a connect timeout with no text, an error with no cause, and a secret in the text of the transport error, each through the investigation.
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_investigation.py`
- [x] 1.2 Add the phase and the first error of the cause chain to the message of `model_call_error`, masked and cut with `bounded_text`.
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_investigation.py`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
