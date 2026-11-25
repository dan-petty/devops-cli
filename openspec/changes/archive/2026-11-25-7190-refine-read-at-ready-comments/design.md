# Design

## Decisions
- **Reuse `_since_wait_start` and `_read_at` in `_has_trusted_comment_since_last_round`**: When `comments` contains a `CONST_ROADMAP_REFINE_COMMENT_MARKER` comment, `_has_trusted_comment_since_last_round` delegates directly to `any(trusted(c) for c in _since_wait_start(item, comments))` (`src/devops_cli/roadmap/refine/refine.py:2913-2932`). When no marker comment is present yet, it reads `read_at = _read_at(item)` (`src/devops_cli/roadmap/refine/refine.py:2893-2903`) and accepts trusted non-job comments with `as_utc(comment.created_at) > read_at`.
- **Replace `REPEATED_AT` test seeding in `test_roadmap_refine_ready_edits.py` with `READ_AT`**: Every written non-failed refine round writes `RefineRecordKey.READ_AT` and clears `RefineRecordKey.REPEATED_AT` (`src/devops_cli/roadmap/refine/refine.py:4817-4819`). Updating `test_roadmap_refine_ready_edits.py` and `openspec/specs/roadmap-refine/selection/spec.md` aligns `#6452` with `#6371`.

## Rejected alternatives
- **Re-introduce `_repeated_at` alongside `_read_at`**: Rejected because `#6371` (`44fb86a04`) intentionally retired writing `RefineRecordKey.REPEATED_AT` and clears it on every written round (`src/devops_cli/roadmap/refine/refine.py:4817-4819`), and `openspec/specs/roadmap-refine/comments/spec.md:38` requires writing `refine.read_at` only.
- **Duplicate timestamp comparison math inside `_has_trusted_comment_since_last_round`**: Rejected because `_since_wait_start` (`src/devops_cli/roadmap/refine/refine.py:2913-2932`) already implements the exact same-tick post and `read_at` boundary logic tested by `tests/roadmap/refine/test_roadmap_refine_event_comment.py`.
