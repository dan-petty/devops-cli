# Design

## Decisions

- **Match a trigger word with a look-around on letters**: `(?<![a-z])word(?:e?s)?(?![a-z])` with `re.IGNORECASE`. A letter on either side ends the match, so `regression` does not match `egress`. An underscore, a hyphen or a digit does not end it, so the identifier `egress_policy` still matches. The pattern for each word is compiled once at import.
- **Allow a plural ending**: `credentials` and `sanitizers` name the same trigger as the singular, so the old substring match found them and the new match must too.
- **Keep paths as substrings**: a trigger path such as `k8s/` is a path prefix, and a longer path holds it on purpose.

## Rejected alternatives

- **`\b` word boundaries**: `\b` treats an underscore as a word character, so `egress_policy` and `keyring_password` would stop matching. The substring match found them.
- **A word list of known false positives**: a list grows with each new word. A rule on word edges has no list.
- **Drop `egress` from the trigger list**: the word is a real trigger for SECURITY.md work on egress policy.
