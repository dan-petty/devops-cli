# Tasks

## 1. Write the status comment on the pull request

Reads: `src/devops_cli/roadmap/implement/implement_run.py`. Changes: the same file and `tests/roadmap/implement/test_roadmap_implement_job.py`.

- [ ] 1.1 Let `_comment` take an `extra` text and put it above the table.
- [ ] 1.2 Move the stop text build before the comments and call `_comment` when `self.pull` is set.
- [ ] 1.3 Add the test of the stop comment on the pull request.
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_job.py` passes
