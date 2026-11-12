## ADDED Requirements

### Requirement: The reason comment holds only the facts that the labels do not show
The intake reason comment SHALL give only a scope with no declared label, the reason of a Priority other than P2-Medium or of a P0 decision on evidence, the possible original and the related item. It SHALL not state the type, scope, Value, Effort or milestone again. With no such fact, intake SHALL post no reason comment.

#### Scenario: The usual fields and no related item
- **WHEN** the model proposes P2-Medium, cites no evidence and names no possible original or related item
- **THEN** intake sets the labels and posts no reason comment

#### Scenario: A related item
- **WHEN** the model names a related item and proposes P2-Medium
- **THEN** the reason comment holds one line, which links the related item and gives its reason

#### Scenario: A Priority other than P2-Medium
- **WHEN** the model proposes P1-High with a reason, and the type, Value and Effort
- **THEN** the reason comment holds the Priority and its reason, and no line for the type, Value or Effort
