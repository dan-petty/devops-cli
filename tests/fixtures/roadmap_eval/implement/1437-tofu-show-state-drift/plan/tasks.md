# Tasks

## 1. State inspection and drift detection via OpenTofu CLI

- [ ] Write failing unit tests for `parse_show_state`, module resources handling, encrypted state parsing, `parse_plan_drift`, and uninitialized directory reporting in `tests/test_tf_analysis.py` and `tests/test_tf.py` (`uv run devops ci test tests/test_tf_analysis.py tests/test_tf.py`).
- [ ] Implement `parse_show_state`, `parse_plan_drift`, `read_state`, `read_plan_drift`, and update `detect_drift` in `src/devops_cli/tf/analysis.py` (`uv run devops ci test tests/test_tf_analysis.py`).
- [ ] Update `devops tf drift` command and language messages in `src/devops_cli/commands/tf.py` and `src/devops_cli/lang/en/messages.py` (`uv run devops ci test tests/test_tf.py`).
- [ ] Delete `load_state`, `_project_state_resource`, `resolve_state_file`, and the prefix-based provider guess, and remove obsolete tests (`uv run devops ci test tests/test_tf_analysis.py`).
- [ ] Regenerate documentation and check readiness (`uv run devops docs generate --sync-readme`).

Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
