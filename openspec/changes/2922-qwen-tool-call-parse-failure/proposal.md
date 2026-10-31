# Proposal

## Why

Issue #2922. The implement Job for #2747 stopped at group 1 with the reason `ModelHTTPError: HTTP 400, model devops-coder, body: litellm.BadRequestError: Ollama_chatException - KeyError: <text>, Got unexpected response from Ollama: {<text>: <text>}`. The stop of #2656 on the day before had the same cause. Two faults hide the cause:

- The text of the body hides every quoted word (#2794), so the words `XML syntax error on line 70: unexpected EOF` are not in the comment.
- The comment does not say that the provider could not parse a tool call of the model.

The cause itself is in Ollama (see Feasibility). A new sample of the model can be whole, but the second send of #2797 failed too, so the step discarded its work.

## What Changes

- `body_error_text` keeps the quoted words of the error text of a body. It still masks the text with `mask_secrets`, cuts it to `CONST_ROADMAP_RUN_ERROR_CHARS` characters, keeps the first line, and stops at the first `=` or `;`. That stop is where the echo of the model begins in `raw='...'` of Ollama. A quoted secret is hidden by the masker, as it is in every other stop text.
- The reason of a step that a failed model call ended gets one more line when the call failed inside an open stream with the status 400 (the error that the step sends again). The line says that the provider failed inside the stream, that tool call parsing failed is a known cause, and names the upstream issue. The line comes from the fields of the error (`in_stream`, `status_code`), not from its text, so it holds for every model.
- No manifest changes, no new model route, no new prompt rule. The evidence in Feasibility does not support them (see the design).
- A consumer observes the reason, so the change carries a spec delta. It modifies one requirement of `roadmap-implement-step`.
- This change fits one pull request.

## Capabilities

### Modified Capabilities

- `roadmap-implement-step`: the reason of a failed model call keeps the quoted words of the error text, and names the failure of the generation inside a stream.

## Impact

- `src/devops_cli/roadmap/agent_run.py`, `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/lang/en/messages.py`.
- `tests/roadmap/test_roadmap_implement_step.py`.
- The documents that `devops docs generate --sync-readme` writes.

## Feasibility

All facts are from 2026-10-31. The cluster reads were read-only. The probes used 5 requests on one pod, one at a time (the budget was 6).

- **The pinned image is the newest that matters.** The pod behind `devops-coder` runs `ollama/ollama:0.40.12` (`ollama --version` in the pod, and the pin in `k8s/llm/profiles/ollama-profiles.yaml`; image digest `sha256:20d1bbfbabe1c97ba4b16301f08a20d8484bcf77047742a3cb71c613d8e12d0b`). The newest release is v0.40.13 (2026-10-28). The compare `v0.40.12...v0.40.13` changes no file under `model/parsers/`, so a bump does not change the parser.
- **The cause is the strict parser of Ollama.** The source of `model/parsers/qwen3coder.go` at v0.40.12 cuts the call at the first `</tool_call>`, rewrites `<parameter=x>` into XML tags, and runs `xml.Unmarshal`. On an error `Add` logs `qwen tool call parsing failed` and returns the error (line 87 in the pod log). The XML error comes when the call is not balanced: the model drops a `</parameter>` or `</function>`, or the value holds tool markup such as `<parameter=...>` that the parser counts as a tag. An unfinished call (no `</tool_call>`) is not an error: the parser returns it as content. So the model wrote `</tool_call>` and the XML before it was not whole.
- **It is a known upstream bug with no fix in a release.** ollama/ollama#14834 (`XML syntax error on line 115: unexpected EOF`, open) and #18563 (the parser is strict, long file writes fail on every retry, open) describe it. The only fix, PR #18571 (return the raw call as content, do not repair it), is open and merged in no release. #17276 is closed as a duplicate of #14834.
- **The pod log matches.** In the log of the pod at 19:47:38 and 19:47:49 UTC the warning comes after a generation of 607 and 793 tokens (`eval time` 10.5 s and 11.2 s), with `truncated = 0` and a prompt of about 24000 tokens in a window of 262144. So no limit cut the call.
- **The model file sets no stop token that breaks a call.** `ollama show qwen3-coder:30b` lists `temperature 0.7`, `top_k 20`, `top_p 0.8`, `repeat_penalty 1.05` and the stop strings `<|im_start|>`, `<|im_end|>`, `<|endoftext|>`. The renderer and parser are `qwen3-coder`.
- **Probes of the parser, on the pod.** (1) A plain 40-line module: one whole call. (2) and (3) Content with the literal text `</tool_call>`: the model left the text out, one whole call. (4) Content with the literal markup `<function=edit_file><parameter=path>...`: `qwen3-coder:30b` wrote the markup in its reply and no call (the generation ended, so no error). (5) The same prompt on `qwen3.8:27b`, the model of `devops-chat`: HTTP 500 `XML syntax error on line 9: element <function> closed by </function>`. So tool markup in a value breaks the parser, `devops-chat` has the same parser and fails the same way, and the parse failure of the real step did not repeat on demand with a small prompt.
- **Replay of #2747.** The step cannot be replayed: the failed call came after a conversation of about 24000 tokens that the Job discarded, and the failure depends on one sample of the model. This change does not claim that a replay ends done.
- **The gateway does not recover it.** The routes `devops-coder` and `devops-reasoning` have fallbacks in `k8s/llm/gateway/config.yaml`, but the log of the gateway shows the error raised inside `async_data_generator` after the status 200, and the fallbacks do not run. Both fallback targets use the same Ollama parser.

So the cause is outside this repository, and no change of image, model setting or route is shown to fix it. The change makes the cause readable, as the issue asks first, and names it. When upstream merges a fix, the image pin is the fix.

## Existing Tool Considered

`mask_secrets` (`devops_cli.security.sanitizer`) already finds a secret by its form, so the change removes the blanking of quoted words and keeps the masker. pydantic-ai gives `ModelHTTPError.in_stream` and `.status_code`, which the step already uses for the resend (`_generation_failed`). The change reuses that test for the new line. It builds no parser and no matcher of the provider text. Estimated cost of what it builds: about 15 lines of code, 60 lines of tests, about 60k tokens of agent work, and one hour of elapsed time. The upkeep is small.

The change deletes `_BODY_QUOTED`, the pattern that hides quoted text in `body_error_text`, and the one-sentence rule about quoted parts in the spec.
