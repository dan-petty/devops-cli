## ADDED Requirements

### Requirement: The repeat guard keeps the question of a frame
The fingerprint of a comment SHALL hold the hash of the owner question that a frame in the comment asks, so two frames that differ only in that hash SHALL both post, and the same frame again SHALL be a repeat.

#### Scenario: Two frames that name the place of two questions
- **WHEN** refine posts the frame of one question and then the frame of another question, each with the same place text, and then the second frame again
- **THEN** the item holds the two frames, and the third comment is refused
