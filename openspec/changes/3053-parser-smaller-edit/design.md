# Design

## Decisions

- **The message goes in the last request of the resend, not in a new message.** The conversation of a resend ends with a request that holds the tool returns. One more `UserPromptPart` in that request keeps the order of messages that the provider expects, and the length of the conversation stays equal, so the stall check of `_run_agent` still works. Rejected: a new `ModelRequest`, because two requests in a row are invalid for some providers.
- **The count is per step, in `ToolCallLog`.** The log lives for all turns of a step, so the second parser failure of a step stops the turn, also when a good reply came between them. Rejected: a count per turn, which would give each failure after a good reply a new smaller-edit message and lets a runaway step repeat the cost.
- **The second failure ends the turn; the ladder decides after that.** The turn ends with the provider error, as when the resends run out today. `_moves_tier` still moves a step to the next tier when the ladder holds one, and the step stops with class `parser` when it holds one. The strategy ladder of #3569 owns the order of the tier change, so this change does not change it. Rejected: stop at once on any ladder, which would remove the tier change that exists today and is outside this part.
- **Every resendable failure is a parser failure.** The reason of an in-stream 400 holds the line that names tool call parsing, so the classifier gives `parser`. Rejected: a second test of the error body in the step, which would repeat the classifier and could disagree with it. The class of the run is the one source.
- **The work stays by the keeper.** The step does not reset or keep anything new: `run_step` discards to the last `wip:` commit, as for each stop (#3054). A test holds it.
