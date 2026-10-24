# thinking-stream Specification

## Purpose
Sanitizes thinking blocks from streaming LLM responses and complete text responses with tag counting, thought bounds, and EOF state tracking.

## Requirements

### Requirement: Strip and count unopened closing thinking tags
The system SHALL detect closing thinking tags encountered while outside a thinking block, strip them from clean answer content, and increment an unopened closing tags counter.

#### Scenario: Unopened closing tag stripped and counted
- **WHEN** response content contains a closing thinking tag without an opening tag
- **THEN** the system increments the unopened close tag counter and does not emit the closing tag in clean content

### Requirement: Report unclosed thinking streams at EOF
The system SHALL detect when a response stream terminates while inside a thinking block, set an unclosed stream indicator, and retain buffered thinking without leaking it to clean content.

#### Scenario: Stream terminates inside thinking block
- **WHEN** a token stream ends before closing an active thinking block
- **THEN** the unclosed stream flag is set to true and thinking tokens remain isolated from clean content

### Requirement: Cap thought content and count discarded characters
The system SHALL bound accumulated thought characters to a configurable maximum limit defaulting to 65,536 characters, discard thought characters exceeding the limit, and increment a discarded thought characters counter.

#### Scenario: Thought content exceeds maximum character limit
- **WHEN** thought content exceeds the maximum character limit
- **THEN** only characters up to the limit are retained and excess characters are recorded in discarded thought characters

### Requirement: Configurable initial sanitizer state
The system SHALL support configuring the initial state as either emitting or thinking, allowing models that pre-open thinking to start directly in the thinking state.

#### Scenario: Initial state configured to thinking
- **WHEN** a model profile configures initial state as thinking
- **THEN** the stream processor starts in the thinking state before encountering an opening tag
