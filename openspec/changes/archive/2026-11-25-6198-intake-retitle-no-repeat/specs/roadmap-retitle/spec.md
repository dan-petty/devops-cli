## ADDED Requirements

### Requirement: The retitle comment omits the After line
When `devops roadmap retitle` changes an item title, its posted comment SHALL keep the explanation, length counts, source, and `- Before:` line, and MUST NOT include an `- After:` line or repeat the new title.

#### Scenario: Title shortening omits After line and new title
- **WHEN** retitle shortens an over-limit item title and posts its comment
- **THEN** the comment holds `- Before:` and `- Source of the summary:` and holds neither `- After:` nor the new title

#### Scenario: Type correction omits After line and new title
- **WHEN** retitle corrects an unlisted title type and posts its comment
- **THEN** the comment holds `- Before:` and `- Source of the summary:` and holds neither `- After:` nor the new title
