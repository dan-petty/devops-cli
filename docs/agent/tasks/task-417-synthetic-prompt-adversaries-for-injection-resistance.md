# Task: Synthetic Prompt Adversaries for Injection Resistance (#417)

**Issue**: [#417](https://github.com/dan-petty/devops-cli/issues/417)
**Scope**: scope/ai, scope/security
**Feasibility**: Confirmed against `src/devops_cli/review/analysis.py` and `src/devops_cli/ai/review/pipeline.py`. The review pipeline decouples scanner findings from model stages. G10 checks drop ungrounded or adversarial model output and count rejections in `analysis.json`. `findings.json` and `findings.sarif` remain byte-identical with model stages enabled or disabled.

## Description

A regression corpus of source files containing crafted prompt injection instructions embedded in comments, docstrings, string literals, and filenames. Offline verification tests that scripted fake models obeying embedded instructions have their bad reply parts individually dropped and counted by G10 checks, while `findings.json` and `findings.sarif` remain byte-identical whether model stages are enabled or disabled.

## Acceptance Criteria

- [x] A corpus of source files carrying embedded injection instructions in comments, docstrings, string literals, and filenames exists in `tests/fixtures/prompt_adversaries/` (`tests/test_review_prompt_adversaries.py:test_adversary_corpus_discovery_and_content`).
- [x] An offline test runs the corpus through the review pipeline with a scripted fake model that obeys embedded instructions, and asserts that each bad reply part is dropped and counted (`tests/test_review_prompt_adversaries.py:test_adversary_corpus_pipeline_drops_and_counts_bad_reply_parts`).
- [x] The offline test asserts findings.json and findings.sarif are byte-identical whether the model stages are on or off (`tests/test_review_prompt_adversaries.py:test_adversary_corpus_findings_json_and_sarif_byte_identical_with_stage_on_vs_off`).
- Pending a person: Run `devops review path tests/fixtures/prompt_adversaries/` against the real model pool and record a per-file table verifying that the model's explanation or plan did not repeat or follow the embedded instructions.

## Deliverables

- [x] Fixture corpus in `tests/fixtures/prompt_adversaries/` covering comments, docstrings, string literals, filenames, and manifests.
- [x] Offline test suite in `tests/test_review_prompt_adversaries.py` asserting corpus collection, reply drop counting, and findings byte-identity.
- [x] Task tracking documentation in `docs/agent/tasks/task-417-synthetic-prompt-adversaries-for-injection-resistance.md`.
