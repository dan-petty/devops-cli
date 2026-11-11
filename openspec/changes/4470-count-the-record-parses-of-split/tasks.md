# Tasks

## 1. Test the parse cost of split_record
kind: other

- [x] 1.1 Add `tests/roadmap/stores/test_roadmap_store_record_parse.py`: a body without the record opener gives 0 parses and `(body, {})`, 100 bodies of which 10 hold the opener give 10 parses and 10 records, and the parse of `Plain text.` and a record block gives an `inline` token with empty `children`.
  - Verification: `$ uv run devops ci test tests/roadmap/stores/test_roadmap_store_record_parse.py`
- [x] 1.2 Show that each test fails on 6cf78e73, the base of the pull request of #4445.
  - Verification: in a scratch worktree at 6cf78e73, commit the new test module and run `devops ci fail-to-pass --base 6cf78e73`. The result is "3 failed on base".
