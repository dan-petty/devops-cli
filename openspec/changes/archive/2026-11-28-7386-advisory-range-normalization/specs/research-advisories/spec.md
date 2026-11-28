## MODIFIED Requirements

### Requirement: The range of an advisory is matched with packaging
The command SHALL match a pinned version to a GitHub advisory range with `packaging`, normalizing bare versions to `==`, stripping a leading `v` or trailing `-stable`, and closing an open lower-bound alternative at `fixed_version` when set. Ranges joined by `||` match when any holds; empty or unreadable ranges stay a failure.

#### Scenario: The edge of a range
- **WHEN** the pinned version is `45.0.7` and the range is `<= 45.0.7`, or the version is `41.0.0` and the range is `< 41`
- **THEN** the first is in the range and the second is not

#### Scenario: Ranges joined with ||
- **WHEN** the range is `>= 3.0.0, < 3.3.15 || >= 3.4.0, < 3.4.10 || >= 3.5.0, < 3.5.4`
- **THEN** `3.5.3` is in the range and `3.5.4` is not

#### Scenario: A range that cannot be read
- **WHEN** an advisory of a mapped repository has the range `since the start`, or an unknown suffix such as `< 1.83.10-custom`
- **THEN** the report holds no finding for it and holds a failure that names the advisory and the invalid suffix

#### Scenario: Bare versions, leading v, and -stable suffixes
- **WHEN** `in_range` matches ranges `"0.6.5"`, `"v0.1.111"`, `"< 1.83.10-stable"`, and `">= v1.82.0-stable, < v1.83.0-stable"`
- **THEN** `"0.6.5"` matches only `0.6.5`, `"v0.1.111"` matches only `0.1.111`, and `"-stable"` matches as the underlying release version

#### Scenario: Open lower-bound range with patched version
- **WHEN** `_github_matches` evaluates a vulnerability with `vulnerable_version_range` `">= 1.86.0"` and `patched_versions` `"1.86.3"` against pin `"1.111.0"` and pin `"1.86.2"`
- **THEN** `"1.111.0"` is not affected and `"1.86.2"` is affected
