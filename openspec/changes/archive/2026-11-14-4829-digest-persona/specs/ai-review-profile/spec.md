## ADDED Requirements

### Requirement: The prompt digest covers the review prompts only
`review_prompt_digest` SHALL hash each `.md` file under `ai/tasks/` and SHALL NOT read `ai/personas/`.

#### Scenario: An edit of a chat persona
- **WHEN** `ai/personas/challenger/prompt.md` changes
- **THEN** `review_prompt_digest()` does not change

#### Scenario: An edit of a review prompt
- **WHEN** `ai/tasks/review_group_analysis.md` changes
- **THEN** `review_prompt_digest()` changes
