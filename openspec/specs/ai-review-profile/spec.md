# ai-review-profile Specification

## Purpose
The review profile records what a review ran with: its prompt digest, the versions of the tools that ran and its own source state. The prompt digest moves only with a prompt that a review loads.

## Requirements

### Requirement: The prompt digest covers the review prompts only
`review_prompt_digest` SHALL hash each `.md` file under `ai/tasks/` and SHALL NOT read `ai/personas/`.

#### Scenario: An edit of a chat persona
- **WHEN** `ai/personas/challenger/prompt.md` changes
- **THEN** `review_prompt_digest()` does not change

#### Scenario: An edit of a review prompt
- **WHEN** `ai/tasks/review_group_analysis.md` changes
- **THEN** `review_prompt_digest()` changes

### Requirement: The profile hashes the versions of the tools that ran
The review profile SHALL hold `tool_versions_digest`, the digest of the tool, the version and the binary digest of each tool run of the review. It SHALL be empty when no tool ran.

#### Scenario: Another installed Semgrep
- **WHEN** a test builds a profile with a run of Semgrep `1.0.0`, again with the same run, and with a run of Semgrep `1.1.0`
- **THEN** the first two digests are equal, the third differs, and a profile with no run has an empty digest
