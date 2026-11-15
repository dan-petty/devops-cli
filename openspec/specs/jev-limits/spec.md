# jev-limits Specification

## Purpose
The context window of the Jev decision model and the diff cap of the roadmap completeness check, both read from the model data of genai-prices rather than a fixed constant.

## Requirements

### Requirement: The window comes from the model data
`context_window` SHALL return the `context_window` that genai-prices gives for the model named by `CONST_AI_JEV_MODEL`, and SHALL return `CONST_AI_JEV_CONTEXT_WINDOW` only when the data names no window for that model.

#### Scenario: The pinned model
- **WHEN** a test calls `context_window()` for `typesafe/jev-1.14`
- **THEN** it returns 32000

### Requirement: The diff cap is a fourth of the window
`max_diff_tokens` SHALL return `context_window() // 4`, and the Jev completeness check SHALL skip a diff over that value.

#### Scenario: The cap
- **WHEN** a test calls `max_diff_tokens()`
- **THEN** it returns 8000

#### Scenario: The committed eval set
- **WHEN** a test reads the completeness cases
- **THEN** every diff holds at most `max_diff_tokens()` tokens
