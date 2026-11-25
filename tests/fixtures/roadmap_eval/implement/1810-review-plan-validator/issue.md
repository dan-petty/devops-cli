`run_review_plan_job` (`src/devops_cli/review/analysis.py`) asks the model for the review plan with `chat(...)` and no validator, so the response cache stores the reply whether or not it parses and passes `verify_review_plan`, and the client may resend an unusable reply up to four more times. #1013 fixed this for the group-analysis call: a validator built from the job's own parse and G10 checks, `max_retries=0`, and a `ReplyRejectedError` handler that reads the finish reason from the rejected reply.

## Evidence

- `run_review_plan_job` calls `llm_client.chat(...)` at `analysis.py` with `temperature`, `top_p` and `seed` only, and parses and verifies the reply afterwards.
- No caller passes `plan_client` to `run_group_analysis`: the pipeline's call (`pipeline.py`, group analysis) passes none, and the only other reference is the parameter itself. The job therefore never runs outside tests, and no plan reply reaches the cache today.
- #1013's plan said whichever of #1148 and #1013 landed second would give the plan job a validator built the same way. #1013 left it out because the job is unreachable and has no test that calls it through a client.

## Proposed remedy

When a `plan_client` is wired into the pipeline, give the plan job the same shape as the group job: a judge function that parses and runs `verify_review_plan` once, `max_retries=0`, and one `ReplyRejectedError` branch. Share the chat-and-judge step between the two jobs instead of copying it. Do this in the PR that wires the client, so the code is exercised by a test through a real client.
