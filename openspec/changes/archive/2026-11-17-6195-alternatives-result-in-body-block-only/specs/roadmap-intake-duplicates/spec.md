## ADDED Requirements

### Requirement: Intake compares the text that a person wrote
Intake SHALL compare a candidate with the text that a person wrote in each item: the body without the block of the alternatives job and without the section of refine. The embedding of an item and its excerpt in the shortlist SHALL hold no text of a job. A duplicate verdict SHALL still place the candidate and name the possible original.

#### Scenario: An item with the block and the section of jobs
- **WHEN** an item holds a person's text, the block of the alternatives job and the section of refine, and the model names the item as the original of a candidate
- **THEN** intake embeds the title and the person's text of the item, the shortlist excerpt holds only the person's text, and the reason comment of the candidate names the item as the possible original
