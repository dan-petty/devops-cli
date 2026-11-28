# Design

## Decisions
- Normalize comparators inside `_specifier_set` in `src/devops_cli/research/version_match.py` so every range form shares one path before constructing `packaging.specifiers.SpecifierSet`.
- For each comparator in `comparators.split(",")`: detect an optional operator from `("===", "==", "!=", "<=", ">=", "~=", "=", "<", ">")`, map `=` or no operator to `==`, and strip a leading `v` and trailing `-stable` from the version token.
- Add optional `patched_version: str | None = None` to `in_range` and `_specifier_set`. When `patched_version` is non-empty, normalize it and append `< <patched_version>` to any `||` alternative whose normalized `SpecifierSet` has no upper-bounding operator (`<`, `<=`, `==`, `===`).
- Pass `patched_version=vulnerability.fixed_version` from `_github_matches` in `src/devops_cli/research/advisories.py`.

## Rejected alternatives
- Normalizing ranges only in `src/devops_cli/research/advisories.py`: rejected because `in_range` and its direct callers/tests would retain the failures for bare versions, `v` prefixes, `-stable`, and `patched_version`.
- Stripping arbitrary `-<tag>` suffixes before `SpecifierSet`: rejected because it could corrupt prerelease or variant tags; only `-stable` is stripped while unknown suffixes continue raising `InvalidSpecifier` (which subclasses `ValueError`).
- Writing a custom version range parser instead of `packaging`: rejected because `packaging` already implements PEP 440 comparisons accurately.
