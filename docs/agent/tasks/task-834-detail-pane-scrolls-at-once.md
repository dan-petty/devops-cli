# Task: The Finding Detail Pane Scrolls to the Top Before the Next Refresh (#834)

**Issue**: [#834](https://github.com/dan-petty/devops-cli/issues/834)
**Status**: Done
**Milestone**: v0.2.24
**Priority**: priority/p0-critical
**Scope**: scope/cli

## Description
87076d5 (#684) made the dashboard's finding detail pane open each newly highlighted finding at the top with `scroll_home(animate=False)`. In Textual 8.2.8, that call defers the scroll until after the next screen refresh. `test_another_finding_is_detailed_from_the_top` read `scroll_y` before that refresh on GitHub's runner, which showed the new finding still scrolled 40 lines down, so CI on `release/v0.2.24` failed intermittently.

## Acceptance Criteria
- [x] `ReviewPanel._show_finding` scrolls the pane to the top with `immediate=True`. The top needs no layout of the new text.
- [x] `test_highlighting_another_finding_scrolls_the_pane_up_at_once` calls the row-highlight handler with another finding on a pane scrolled to 40 and reads `scroll_y` with no pause: `(40, 0, "Title: Finding 2")`. Against 87076d5 it gave `(40, 40, "Title: Finding 2")`.
- [x] `test_another_finding_is_detailed_from_the_top` and the other detail-pane tests passed 20 consecutive runs under `-n 8`.
- [x] `uv run devops ci` passes.
