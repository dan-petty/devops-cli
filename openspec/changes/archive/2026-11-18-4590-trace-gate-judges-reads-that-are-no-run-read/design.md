# Design

## Trace Gate Parsing Updates

### 1. Relative-Clause Reads
When a read verb is introduced by a relative pronoun (`that`, `which`, `who`), its object is either in `obj` after the verb or in the antecedent clause before the pronoun. When neither holds a path, the read does not claim a path read, so `_object_span` returns `None` rather than falling back to the previous path in the sentence.

### 2. Parenthesized Citations on Code Subjects
`_CODE_READS` accepts an optional parenthesized citation after the code span, such as `` `collect_context` (`src/x.py`) reads ``.

### 3. Plural Code Spans as Subject
`_PLURAL_CODE_READ` matches a list of code spans joined by `and` or `or`. `_is_code_reading` checks this pattern when the verb is `read`.

### 4. Negation with `cannot`
`_NEGATION` adds `cannot` alongside `not`, `never`, `no`, `without`, `neither`, `nor`.

### 5. Trailing Line Ranges
`_citation` strips trailing ` <start>-<end>` ranges from spans that look like file paths.
