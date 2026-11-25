## Problem
`Tests & Coverage` of main fails at 2b4ae1f67 (run 43995284368), so every pull request and release 0.169.3 (#6093) fail `Tests on Main`:

`tests/roadmap/stage/test_roadmap_stage_window.py::test_a_first_request_of_code_with_the_context_and_the_body_at_their_caps_offers_the_tools`: `assert (True, False) == (True, True)`.

The first plan request, with code at the context and body caps, counts 49,193 tokens; the limit where the run offers no tool is 49,152 (window 65,536). #6091 added 243 tokens to `src/devops_cli/ai/tasks/roadmap_stage_change.md` (6,289 to 6,532). Each pull request passed alone: #6091 ran on be2b4c11c, before #6078 and the other merges, and the test passes at f592ce776, the commit before #6091. Strict up-to-date is off on purpose (merge skew).

## Expected behavior
- The first request at the caps stays under the limit with room for a small prompt change: lower `CONST_ROADMAP_STAGE_CONTEXT_MAX_TOKENS` (the repository context, which the tools can read on demand), and correct the stale count in its comment.
- Main passes `Tests & Coverage` again.


<!-- devops-roadmap-record {"Effort": "Low", "Priority": "P1-High", "Status": "In Progress", "Value": "High"} -->
