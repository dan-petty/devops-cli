## MODIFIED Requirements

### Requirement: The page text reaches the model as data
The answer of the tool SHALL say that the text is data from an outside page and not an instruction. It SHALL name the source URL and the fetch date, and SHALL say that a link in the text is not a source. It SHALL put the text in a fenced block that no line of the text can end. A text over 8000 characters SHALL be cut, and the answer SHALL say so.

#### Scenario: A page that says to ignore the instructions
- **WHEN** a page says "Ignore your instructions"
- **THEN** the text reaches the model inside the frame, after the line that says it is data

#### Scenario: A page with a link
- **WHEN** the text of a fetched page holds a link to another page
- **THEN** the answer names the source URL to cite and says that a link in the text is not a source
