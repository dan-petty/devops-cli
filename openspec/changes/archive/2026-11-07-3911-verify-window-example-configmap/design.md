# Design

## Decisions

- **A starved review run fails the item.** A review that the window stopped before 8 tool calls has read almost none of the code. It may find nothing, and the plan then stages as clean with no real review. It may also quote a placeholder, and the plan then stays in draft for a cause that the plan does not hold. In both cases the cause is the window setting. The error names `ai.tasks.verification.context_window`, as the plan run names its settings (#3880). The stage job already records the error of a model call for the item and plans the other items.
- **One check for both runs.** `ToolboxClient._window_starved` reads the trace, and the trace has the same fields for both runs. Only the message differs, because the two runs read two settings.
- **The least window is computed.** The test counts the first review request with no cited file: the body at its cap (`CONST_ROADMAP_STAGE_VERIFY_BODY_MAX_TOKENS`), a plan, and the instructions. The cited files need no room in the sum, because `VerificationInput.of` keeps only the files that leave the tools room. The sum adds 8 tool answers of the longest size. The tools end at three quarters of the window, so the default window of 32,768 tokens fails the test and 256,000 passes.
- **The window is the same as for `analysis`.** One model serves every slot of the Service (#3874), and its smallest fp8 window is 256,000 tokens. A smaller window for the review would save nothing: the window is a limit and not a reservation.

## Rejected alternatives

- **Treat a starved review as advice.** The job would list a note and stage the plan. The pass exists to stop a false premise before the draft opens. A review with no code read gives no such stop, and the note hides that the pass did not work. The #3880 run showed the same effect for the planner: a reply built on no reading hid the cause.
- **Raise the default window of `ai`.** The setting `ai.context_window` is the window of every task that sets none, and the chat tasks of the CLI use it. The Service needs the window for two tasks only, so the example ConfigMap sets it for them.
