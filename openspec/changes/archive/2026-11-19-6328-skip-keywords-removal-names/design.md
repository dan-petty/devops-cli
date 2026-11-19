# Design

## Decisions

- Use the standard-library `keyword` module. A span is a removed name only when `span.isidentifier()` is true, `keyword.iskeyword(span)` is false and `keyword.issoftkeyword(span)` is false.
- Put the rule in one private helper, `_is_removable_identifier(span)`. The passive match loop and the active match loop both call it, so the two paths keep one rule.

## Rejected alternatives

- A keyword tuple in the project: it copies the list of CPython and does not follow a new Python release. On CPython 3.14.10 the soft keyword list holds `type`, which a hand-made list of hard keywords misses.
- A parser library such as libcst: it adds a dependency for a membership test that the standard library answers.
- Keep only `str.isidentifier()`: `"and".isidentifier()` is true, which is the cause of the stage failure of #6328.
- Filter the final set: the scan builds its patterns from the set, and a filter at the end hides which span the extraction refused. The helper keeps the rule at the point where each span is read.
