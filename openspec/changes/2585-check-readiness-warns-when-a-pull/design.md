# Design

## Decisions

- **Place the 1,000-character constant and the trailer-prefix tuple in `merge_readiness.py` beside the rule's reader.**: The issue body says "The limit is one constant beside the rule's reader." One module reads it, so it stays local per the naming rules in CONTRIBUTING.md section 5.
- **Strip trailers by a closed list of five known prefixes.**: The body names the exact set. A closed list is the project's standard for a closed domain (CONTRIBUTING.md section 1, Closed Lists and Standard Parsers).
- **Use the existing `_Verdict.warn()` path for the advisory.**: `AdvisoryLevel` docstring states "no advisory changes an exit code." The advisory is separate from blockers in the `MergeReadiness` dataclass. No new mechanism is needed.
- **Name the actual length, the limit, and CONTRIBUTING.md section 4 in the advisory text.**: The issue body specifies this. It is actionable: the writer sees how much to cut and where the rule lives.

## Rejected alternatives

- **Use a generic trailer parser (e.g. `git interpret-trailers`).**: Overkill for five known prefixes. Adds a dependency for a fixed set. The closed-list rule in CONTRIBUTING.md section 1 applies.
- **Place the constant in `config/constants.py`.**: The issue body says "beside the rule's reader," not in config. No second package imports it. CONTRIBUTING.md section 5 says a constant stays in the one module that reads it.
- **Name only the length in the advisory text.**: Less actionable. The writer must find the limit and the rule on their own. The issue body specifies naming the length, the limit, and CONTRIBUTING.md section 4.
