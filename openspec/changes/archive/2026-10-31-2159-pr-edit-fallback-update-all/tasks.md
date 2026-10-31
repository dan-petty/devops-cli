## 1. Failing Tests First

- [x] 1.1 Add failing test for `devops pr edit` REST fallback covering title, body, base, milestone, and milestone failure
- [x] 1.2 Add failing test for `devops pr update --all --dry-run` planned requests with and without `--dispatch-ci`
- [x] 1.3 Add failing test for `devops pr update --all` execution over candidate pull requests (order, drafts, empty list)

## 2. Test Verification and Alignment

- [x] 2.1 Verify tests pass with `process_fake` and `cli` fixture without patching `devops_cli` names
- [x] 2.2 Verify full CI checks pass and archive change
