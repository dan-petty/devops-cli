# Spec Delta

## MODIFIED Requirements

### Requirement: The refine proposal context is capped by a job constant
The refine job SHALL cap the token budget of the repository context for proposal generation to `CONST_ROADMAP_REFINE_CONTEXT_MAX_TOKENS`, 20,480 tokens, or the model context window divided by 2, whichever is smaller.

#### Scenario: Proposal context with a large model window
- **WHEN** the context window of the task `refine` is 256,000 and cited context exceeds 20,480 tokens
- **THEN** the proposal context holds at most 20,480 tokens
