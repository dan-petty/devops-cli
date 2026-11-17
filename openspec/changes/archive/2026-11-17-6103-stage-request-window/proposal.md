# Proposal: #6103

## Why

Issue #6103: `Tests & Coverage` of `main` fails at 2b4ae1f67 on `tests/roadmap/stage/test_roadmap_stage_window.py::test_a_first_request_of_code_with_the_context_and_the_body_at_their_caps_offers_the_tools`. The first plan request, with code at the context and body caps, counts 49,193 tokens, and the run offers no tool at 49,152 (window 65,536). #6091 added 243 tokens to the stage prompt. It passed on its own base, before #6078 merged.

## What Changes

- `CONST_ROADMAP_STAGE_CONTEXT_MAX_TOKENS` goes from 20,480 to 19,456 tokens. The first request keeps about 1,000 tokens for a change of the stage prompt. The tools of the run read more context on demand. The body cap and the tool reserve stay.
- The window test also asks for 512 tokens of room below the limit, so a small prompt change cannot take the request over it again.
- The change has no spec delta and sets `skip_specs: true`: the requirements of `roadmap-stage/run-limits` name the constant, not its value.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- The first plan request of the stage job holds 1,024 fewer tokens of repository context.
- `docs/roadmap/stage.md` gives the new cap.

## Feasibility

- On 2b4ae1f67 the first request counts 49,193 tokens against a limit of 49,152. The prompt counts 6,532 tokens, and 6,289 at f592ce776, the commit before #6091.
- The test passes at f592ce776, 88aa191b0 and 19bfec309, and fails at 2b4ae1f67.
- With the new cap, `tests/roadmap/stage/` gives 3017 passed.

## Existing Tool Considered

None applies: the cap is a constant of the stage job.
