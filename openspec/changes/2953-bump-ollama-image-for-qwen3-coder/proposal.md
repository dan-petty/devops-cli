# Proposal: #2953

## Why

The implement job stops on a large edit when the `qwen3-coder` parser of Ollama fails (#2656, #2747). The cause is upstream (ollama/ollama#14834 and #18563). The item says to wait for a release that holds the fix of PR #18571. The owner decided to bump the image now, to keep the pin current and to move the pin to the form of tag and digest. Closes #2953.

## What Changes

- Change the image of every Ollama container in `k8s/llm/profiles/ollama-profiles.yaml` and `k8s/llm/profiles/tier-templates/ollama-48gib-slow.yaml` from `ollama/ollama:0.40.12` to `ollama/ollama:0.40.16@sha256:910d0d8107b538fb0894e63163eb195de0cc7aefcbc666dc62d3b18f71124592`.
- Widen `tests/invariants/test_k8s_manifests.py` and `tests/core/test_renovate_config.py` to accept the form `tag@sha256:digest`.

## Capabilities

No capability changes. The pin of one third-party image moves.

## Impact

Every Ollama tier runs v0.40.16. The change does not fix the parser failure (see Feasibility). The failure can come back on a large `edit_file` call, and #2953 stays a place to track the real fix.

## Feasibility

Checked on 2026-11-10 against upstream:

- ollama/ollama PR 18571 is `open`, not merged.
- `compare v0.40.12...v0.40.16` changes only `model/parsers/mimo_test.go`, `parsers.go`, `ripple.go` and `ripple_test.go`. Nothing changes the qwen3-coder parser.
- Tag 0.40.16 exists on Docker Hub. Its index digest is `sha256:910d0d81…4592`.

So this change does not meet the acceptance criterion "a replay of a large `edit_file` call parses". No replay of the original failure is possible: it depended on one sample of the model after a conversation of about 24,000 tokens that the Job discarded (see the archive of #2922). The owner chose to bump with this knowledge. The item must stay open for the parser fix: the pull request does not use `Closes`.

## Existing Tool Considered

Renovate (kubernetes manager) opens this bump on its own. The owner asked for the change now, and the tests need the digest form in the same pull request.
