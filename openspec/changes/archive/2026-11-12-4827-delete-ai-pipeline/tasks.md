# Tasks

## 1. Behavior: the review comment names no persona

- [x] 1.1 Change the comment tests so that they expect no `Personas:` line, no `Review by` heading and the new routed-file message, and see them fail
  - Verification: `$ uv run devops ci test tests/commands/test_review_pr_post.py tests/ai/client/test_batch_2_review_defects.py tests/ai/review/test_review_path_routing.py`
- [x] 1.2 Return `ReviewResult | str` items from the review runner, drop the persona from the comment, and rename the routed-file messages
  - Verification: `$ uv run devops ci test src/devops_cli/ai/review/runner.py src/devops_cli/lang/en/messages.py`

## 2. Other: delete the command and the unread code

- [x] 2.1 Delete `devops ai pipeline`, its defaults, help texts, dry-run plan and constant, and its tests
  - Verification: `$ uv run devops ai pipeline --help` exits with `No such command`
- [x] 2.2 Delete `ScratchpadBuffer`, `ScratchpadEntry` and the unread persona fields of `src/devops_cli/models/ai.py`
  - Verification: `$ uv run devops ci test tests/models/test_resource_schemas.py`

## 3. Documents

- [x] 3.1 Fix `ARCHITECTURE.md`, `docs/SELF_IMPROVEMENT.md` and `k8s/README.md`, and regenerate the command and settings references
  - Verification: `$ uv run devops ci docs`
