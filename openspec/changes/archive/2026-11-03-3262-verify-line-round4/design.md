# Design

## Decisions

1. **Call `form_problems` in the split branch, as `check_proposal` does.** A split reply has no other check of the `verify` form. The same function keeps one rule.
2. **Only U+FEFF is added to the fold.** The class `\s` of JavaScript has no other character that Python lacks.
3. **HTML tags are refused at the start of a text.** An HTML block runs to a blank line or the end of the file, so it hides the lines after it. A `<` that is followed by a space or a digit is text.
4. **The ratchet reads the declared types.** It fails when a new `str` field has no fold and no named check, so the rule cannot be dropped by a new field.

## Rejected alternatives

- **Run `check_proposal` on the split reply.** Rejected: it checks the spec delta and the tree too, and the split changes the groups only.
- **Strip U+FEFF.** Rejected: a space keeps the words apart, as for any other white space.
