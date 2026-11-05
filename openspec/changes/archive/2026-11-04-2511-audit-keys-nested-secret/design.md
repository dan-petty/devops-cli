# Design

## Decisions

- **Walk the parsed YAML and match the dotted key of each entry against `secret_keys()`**: The walk keeps the order of the keys in the file, so the order of the leaks does not change. It keeps `is_secret_field`, so a secret-named key that is no longer an option is still found, as before. A key that holds a value and matches is a leak, and the walk does not go into it. A key that holds a mapping and does not match is walked.
- **Report the dotted key**: A key of three levels has no `<section>.<key>` form. The leak is `<path>:<dotted key>`, and the table state of a credential still matches by the dotted key.

## Rejected alternatives

- **Navigate each key of `secret_keys()` by its path**: It needs one lookup per credential for each file, and it drops the match of a secret-named key by `is_secret_field`. The walk reads each entry of the file once.
- **Flatten the YAML to all dotted paths and intersect with the registry**: It builds a path list for every key of the file. The walk builds no list.
- **Match the leaf name only**: Two sections can share a leaf name, so it gives false positives.
- **Use detect-secrets**: It decides by content heuristics, not by the registry, and it has no keyring reference or report fields. See Existing Tool Considered in the proposal.
