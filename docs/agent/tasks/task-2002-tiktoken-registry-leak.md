# Task: The Synthetic tiktoken Encoding Leaves the Registry with Its Test (#2002)

**Issue**: [#2002](https://github.com/dan-petty/devops-cli/issues/2002)
**Scope**: scope/ai
**Feasibility**: The pre-push gate of #1995 failed four token-count tests on one xdist worker. `uv run pytest -n 0 -p no:randomly --no-cov` on the prepared-cache test and then `test_truncate_to_token_limit` failed every time: `count_tokens` returned 37 for a 37-character string. tiktoken's `get_encoding` reads the module global `tiktoken.registry.ENCODINGS` and stores each encoding it builds there.

## Description
`_prepare_o200k_cache_dir` removed `o200k_base` from tiktoken's registry with `monkeypatch.delitem(..., raising=False)`. When the key was absent, monkeypatch recorded nothing, so the synthetic encoding that `count_tokens` then built stayed in the registry after the test. The helper now gives the test an empty registry of its own with `monkeypatch.setattr`, and monkeypatch puts the original registry back at teardown.

## Acceptance Criteria
- [x] `test_the_synthetic_encoding_leaves_tiktokens_registry_with_its_test` starts from a registry without `o200k_base`, runs the prepared-cache setup in an inner monkeypatch context, and requires that no `o200k_base` encoding remains. It fails on the base and passes now.
- [x] The ordered run of the prepared-cache test and `test_truncate_to_token_limit` passes.
