# docs-ste-style Specification

## Purpose
The Vale style that checks the hand-written prose against the four ASD-STE100 rules of AGENTS.md rule 9, and its pinned tool.

## Requirements

### Requirement: Vale checks the ASD-STE100 rules
The repository SHALL hold `.vale.ini` and the style `STE` with four suggestion rules: `SentenceLength` for a sentence over 25 words, `ParagraphLength` for a paragraph over 6 sentences, `PassiveVoice` for a form of "be" and a past participle, and `Contractions`. Vale SHALL check each Markdown file with the style and SHALL skip code blocks and code spans.

#### Scenario: A sentence over the limit
- **WHEN** a Markdown file holds a sentence of 26 words
- **THEN** Vale reports one `STE.SentenceLength` alert, and no alert for 25 words

#### Scenario: A contraction
- **WHEN** a Markdown file holds `doesn't`
- **THEN** Vale reports one `STE.Contractions` alert, and no alert for `do not`

#### Scenario: Code
- **WHEN** a code span or a code block holds a contraction
- **THEN** Vale reports no alert

### Requirement: The testing page passes
`vale docs/TESTING.md` SHALL return 0 errors and 0 warnings, with the findings at the suggestion level.

#### Scenario: The page
- **WHEN** the test runs Vale on `docs/TESTING.md`
- **THEN** the exit code is 0 and the output holds `0 errors`
