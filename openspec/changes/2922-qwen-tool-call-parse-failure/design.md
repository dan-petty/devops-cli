# Design

## Decisions

- **Keep the words, mask the secrets.** #2794 hid each quoted part, because Ollama echoes the model in `raw='...'`. That also hid the words of a real error: the quoted keys and strings of `{'error': 'XML syntax error ...'}`. The echo already ends at the first `=`, so the quote rule was a second guard on top of it. The reason now relies on the same guards as every other stop text: the first line, `mask_secrets`, the cut to `CONST_ROADMAP_RUN_ERROR_CHARS` characters, and the stop at the first `=` or `;`. The residual risk is an echo with no `=` and a secret that the masker does not know by form. The diff of the discarded work has the same risk and the same masker.
- **The line that names the failure comes from fields, not text.** `_generation_failed` already tells an error inside an open stream, with the status 400, that is no context window error. That is the shape of every failure of the generation that the provider reports after it sent the status 200. The new line says so and names the known cause. It does not claim that every such error is a parse failure, and it matches no word of the provider text, so it holds for the XML error of `qwen3-coder`, the JSON error of another model, and a later wording of Ollama.
- **No fix of the parser here.** The parser is in Ollama and the fix is not in a release (see the proposal). The image pin is the place of the fix, and only a person syncs it.

## Rejected alternatives

- **An Ollama bump to v0.40.13.** The compare `v0.40.12...v0.40.13` has no change under `model/parsers/`, so the failure stays.
- **A fallback of the step to `devops-chat` after the second parse failure.** `devops-chat` runs `qwen3.8:27b` on the same Ollama and the same parser. A probe with tool markup in a value gave an XML error on that model (proposal, probe 5). No replay shows that another sample is whole more often, and the budget of probes does not allow one. It would add a second model, a constant and a branch for a gain that nobody measured. If a measurement later shows a gain, a new item can add it.
- **A model setting (`temperature`, `repeat_penalty`, `num_predict`).** The pod log shows no truncation, the stop strings are the usual ones, and the failure of #18563 repeats on every retry of one conversation, so a sampling setting does not address it. No probe showed a change by a setting.
- **A rule in the step prompt for smaller edits.** The first successes of #2735 and #2739 were small edits, but there is no measurement that a smaller edit removes the failure, and a prompt rule that nobody can test is a guess. The issue asks for a measurement.
- **A match on the text `XML syntax error` or `tool call parsing failed`.** The provider text is a fact of one parser. The fields of the error say the same for all models. The pod log holds `tool call parsing failed`, and the error body does not.
- **A repair of the tool call by the step.** The step never sees the call: Ollama refuses it before the gateway sends any part of it.
