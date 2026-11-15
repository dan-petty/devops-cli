# Tasks: #5464 fix(roadmap): the refine proposal caps its context with a job constant

- [x] Add `CONST_ROADMAP_REFINE_CONTEXT_MAX_TOKENS = 20_480` to `src/devops_cli/config/constants.py` <!-- id: 0 -->
- [x] Update context cap in `src/devops_cli/roadmap/refine/refine.py` using `_WINDOW_SHARE_CONTEXT` <!-- id: 1 -->
- [x] Return `RefineContext` with `before` and `after` counts from `collect_context` <!-- id: 2 -->
- [x] Record `context_before` and `context_after` on `RefinedItem` and log on result line <!-- id: 3 -->
- [x] Add unit and contract tests in `test_roadmap_refine_proposal.py` and `test_roadmap_refine_job_result.py` <!-- id: 4 -->
