# Design

## Decisions

- **Derive commit type from changed paths**: Changed paths show what the implementation changes. If only `tests/` paths change, use `test`. If only `docs/`, `openspec/`, or `.md` files change, use `docs`. If only `.github/workflows/` or `.github/actions/` change, use `ci`. Other changes keep the issue type. Files under `openspec/changes/` are change metadata and do not prevent a test-only classification.
- **Summary extraction precedence**: Read `## Summary` first line. If absent, check the commit subject plan summary or `## What Changes` first bullet. If absent or invalid, use the issue title summary.
- **Find proposal in archive or active folder**: Check the archived change folder first. If absent, check the active change folder.
- **Validation fallback**: If the derived title fails `title_problems`, fall back to `delivery_title(self.target.item.title, declared)`.
- **Remove stale type labels**: When metadata is updated, remove any `type/*` labels that do not match the new delivery title.

## Rejected alternatives

- **Use issue title type unconditionally**: Rejected because it causes incorrect changelog lines when scope is refined.
- **Use AI model to generate title**: Rejected because it adds latency and non-deterministic behavior.
