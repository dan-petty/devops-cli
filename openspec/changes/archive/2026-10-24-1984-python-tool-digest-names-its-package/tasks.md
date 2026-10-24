# Tasks

## 1. The binary digest of a Python review tool names its installed distribution

- [x] 1.1 Write `test_a_python_tool_digest_names_its_package_not_its_launcher_script`, `test_a_python_tool_version_is_the_version_of_the_distribution_that_runs`, `test_a_python_tool_with_no_record_has_no_digest` and `test_a_native_binary_digest_is_the_digest_of_its_file` in `tests/review/test_review_tool_binary_digest.py`, and verify that `uv run devops ci test tests/review/test_review_tool_binary_digest.py` fails on the base in the first three: the digest is the SHA-256 of the launcher, the version is the pin of `tools.lock`, and a distribution without `RECORD` gives the digest of its launcher
- [x] 1.2 Make `resolve_tool_version_and_sha` in `src/devops_cli/review/canary.py` name the installed distribution whose console script wrote the launcher, and verify that `uv run devops ci test tests/review/test_review_tool_binary_digest.py tests/test_review_canary.py tests/test_tool_executor_contract.py tests/test_review_tool_runs.py` passes
- [x] 1.3 Say what `binary_sha256` covers in the Tool Run Records section of `docs/SELF_IMPROVEMENT.md`, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops docs check` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
