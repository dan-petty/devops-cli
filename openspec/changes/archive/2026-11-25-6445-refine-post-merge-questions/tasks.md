# Tasks

## 1. Behavior (RED -> GREEN)

- [x] 1.1 Add failing tests in `tests/roadmap/refine/test_roadmap_refine_person_wait.py` and update `tests/roadmap/refine/test_roadmap_refine_proposal.py` for merge questions, post-release live-proof questions, pre-build person questions, `roadmap_refine_reply.md` wording, and `CONST_ROADMAP_REFINE_RULES_SINCE`.
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_person_wait.py tests/roadmap/refine/test_roadmap_refine_proposal.py`
- [x] 1.2 Update `src/devops_cli/ai/tasks/roadmap_refine_reply.md`, `src/devops_cli/roadmap/refine/refine.py` (`validate_proposal`), and `src/devops_cli/config/constants.py` (`CONST_ROADMAP_REFINE_RULES_SINCE`).
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_person_wait.py tests/roadmap/refine/test_roadmap_refine_proposal.py`

## 2. Documents

- [x] 2.1 Update `docs/roadmap/refine.md` and run `devops ci docs`, `devops ci fail-to-pass`, and static CI gates.
  - Verification: `$ uv run devops ci docs`
