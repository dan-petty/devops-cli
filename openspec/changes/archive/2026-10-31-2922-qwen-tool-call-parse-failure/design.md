# Design

## Decisions

- **Unwrap the gateway, keep the quote guard.** #2794 hid each quoted part, because Ollama echoes the model in `raw='...'`. That also hid the words of a real error: the quoted keys and strings of `{'error': 'XML syntax error ...'}`. A review showed that dropping the quote guard lets a quoted secret with no `=` and no known form (`"db_password: hunter2"`) reach the public comment. So the guard stays. The reason reads the error text of the one known wrapper, `{'error': '<text>'}` at the end of the line, and drops the other quoted words of the line (`KeyError: 'message'`). The text inside then goes through the same guards as any text: mask, cut, hiding of quoted parts, stop at `=` or `;`. The cause words of Ollama have no quotes, so they show. A quoted part inside the error text is still hidden, which is the safe side.
- **The line that names the failure comes from fields, not text.** `_generation_failed` already tells an error inside an open stream, with the status 400, that is no context window error. That is the shape of every failure of the generation that the provider reports after it sent the status 200. The new line says so and names the known cause. It does not claim that every such error is a parse failure, and it matches no word of the provider text, so it holds for the XML error of `qwen3-coder`, the JSON error of another model, and a later wording of Ollama.
- **No fix of the parser here.** The parser is in Ollama and the fix is not in a release (see the proposal). The image pin is the place of the fix, and only a person syncs it.

## Rejected alternatives

- **An Ollama bump to v0.40.13.** The compare `v0.40.12...v0.40.13` has no change under `model/parsers/`, so the failure stays.
- **A fallback of the step to `devops-chat` after the second parse failure.** `devops-chat` runs `qwen3.8:27b` on the same Ollama and the same parser. A probe with tool markup in a value gave an XML error on that model (proposal, probe 5). No replay shows that another sample is whole more often, and the budget of probes does not allow one. It would add a second model, a constant and a branch for a gain that nobody measured. If a measurement later shows a gain, a new item can add it.
- **A model setting (`temperature`, `repeat_penalty`, `num_predict`).** The pod log shows no truncation, the stop strings are the usual ones, and the failure of #18563 repeats on every retry of one conversation, so a sampling setting does not address it. No probe showed a change by a setting.
- **A rule in the step prompt for smaller edits.** The first successes of #2735 and #2739 were small edits, but there is no measurement that a smaller edit removes the failure, and a prompt rule that nobody can test is a guess. The issue asks for a measurement.
- **A match on the text `XML syntax error` or `tool call parsing failed`.** The provider text is a fact of one parser. The fields of the error say the same for all models. The pod log holds `tool call parsing failed`, and the error body does not.
- **A repair of the tool call by the step.** The step never sees the call: Ollama refuses it before the gateway sends any part of it.
