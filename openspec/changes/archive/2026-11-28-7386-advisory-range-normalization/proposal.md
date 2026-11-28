# Proposal: #7386

## Why
`devops research advisories` exits 1 when a GitHub advisory range omits an operator (`0.6.5`), carries a leading `v` (`v0.1.111`), or ends with `-stable` (`< 1.83.10-stable`), because `_specifier_set` in `src/devops_cli/research/version_match.py` passes the raw text straight to `packaging.specifiers.SpecifierSet` (#7386). `_github_matches` in `src/devops_cli/research/advisories.py` also omits `fixed_version` when matching, so an open lower-bound range (`>= 1.86.0` with `patched_versions: "1.86.3"`) falsely reports newer pins (`1.111.0`) as affected.

## What Changes
- Normalize each comparator in `_specifier_set` (`src/devops_cli/research/version_match.py`): prefix bare versions with `==`, strip a leading `v` from the version, and strip a trailing `-stable` suffix while letting other invalid suffixes raise `InvalidSpecifier`.
- Add `patched_version` to `in_range` so any alternative in `||` without an upper bound (`<`, `<=`, `==`, `===`) is closed with `< <patched_version>`.
- Pass `vulnerability.fixed_version` from `_github_matches` in `src/devops_cli/research/advisories.py` to `in_range`.
- Add unit and advisory-matching tests in `tests/research/test_version_match.py` and `tests/research/test_advisories.py`.

## Capabilities
- `research-advisories`: Normalizes bare versions, `v` prefixes, and `-stable` suffixes in GitHub advisory ranges, and bounds open lower-bound ranges with `patched_version`.

## Impact
- `src/devops_cli/research/version_match.py`: Comparator normalization and patched-version upper-bound support in `_specifier_set` and `in_range`.
- `src/devops_cli/research/advisories.py`: Passes `vulnerability.fixed_version` into `in_range`.
- `tests/research/test_version_match.py`, `tests/research/test_advisories.py`: Regression coverage for all new behaviors.

## Feasibility
Confirmed against `src/devops_cli/research/version_match.py:66-89`, `src/devops_cli/research/github_advisories.py:70-73`, and `src/devops_cli/research/advisories.py:386-393`. `GhsaVulnerability.fixed_version` already exposes `first_patched_version or patched_versions or ""`, and `in_range` is called only by `_github_matches` and unit tests.

## Existing Tool Considered
In-use library: `packaging` (`packaging.specifiers.SpecifierSet` and `packaging.version.Version`). `packaging` handles PEP 440 parsing and comparison after normalizing non-PEP-440 GitHub advisory forms (bare version, leading `v`, `-stable`) and adding `< <patched_version>` on open lower-bound branches, rather than replacing `packaging` with a custom version comparator.
