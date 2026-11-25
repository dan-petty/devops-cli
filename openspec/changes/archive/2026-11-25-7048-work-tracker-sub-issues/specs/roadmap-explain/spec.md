## ADDED Requirements

### Requirement: Explain lists open sub-issues and related open issues for a tracker
When `explain_item` inspects an open tracker (`item.is_tracker`), it SHALL preserve the refine (`refine_left_tracker`) and stage (`stage_left_tracker`) job verdicts while populating the tracker's open sub-issues (with status and open blocker numbers) and open related issue references from person-written body text. `render_explanation` SHALL print these open sub-issues and related open issues for a tracker without changing the output of non-tracker items.

#### Scenario: Explain prints open sub-issues, blocker state, and related issues of a tracker
- **WHEN** `devops roadmap explain` runs on a tracker that has ready unblocked sub-issue `#12`, blocked sub-issue `#13` (waiting on `#12`), and open related issue `#15` in its body
- **THEN** the refine verdict remains `refine_left_tracker`, and the rendered report names open sub-issues `#12` (unblocked) and `#13` (blocked by `#12`) as well as related open issue `#15`

#### Scenario: Explain prints guidance when a tracker has no open sub-issues
- **WHEN** `devops roadmap explain` runs on an open `type/epic` tracker whose open sub-issues and related open issues are empty
- **THEN** the rendered report states that no open sub-issues were found and advises closing if delivered or filing sub-issues
