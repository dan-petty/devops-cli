# Task 583: Roadmap Sync Reads Each Item's Priority From Its Own Tag

**Issue**: [#583](https://github.com/dan-petty/devops-cli/issues/583)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/bug`, `scope/github`, `priority/p1-high`

---

## 1. Description & Objectives

`devops gh sync-roadmap` labels each issue it creates with a priority from `_extract_priority`.
It was given the item's header and every body line, and it returned the first priority whose
keyword appeared anywhere as a substring: `p0`, `blocker` and `critical` first, then `p1` and
`high`, and so on. "Blocker" in a title, or "critical" or "higher" in a description, overrode
the item's own tag.

After the vibes gap entries landed (#580), 19 of the 189 open roadmap items would have been
filed with the wrong label: 17 as P0 and 2 as P1. Examples: "In-Flight Work, PR Stagnation &
Blocker Radar" and "Executable Verification Criteria", both tagged `(P1 - High)`, derived
`priority/p0-critical`.

This was the first step of the roadmap entry "Roadmap Deferrals Recorded Once and Honoured by
Every Sync Path", split out so those entries can be synced with correct labels.

### Key Deliverables Completed:

- [x] **Priority from the item's own tag** (`src/devops_cli/github/roadmap_sync.py`):
  - `_extract_priority` takes the header line only and matches one anchored regex for the
    `(P0 - ...)` to `(P3 - ...)` tag, either inside the bold title, where only further
    parentheticals such as `(Issue #5)` may follow it, or directly after the closing `**`.
  - Only the digit decides the priority; `(P0 - High)` is P0. Tag-shaped title words such as
    `(P1-era)`, backticked calls such as `f(P0 - z)`, and description text never decide it.
  - An untagged header keeps the `priority/p1-high` default.
- [x] **Keyword table removed** (`src/devops_cli/config/constants.py`):
  `CONST_ROADMAP_PRIORITY_TAGS` is replaced by `CONST_ROADMAP_PRIORITY_LABELS`, a map from the
  tag digit to its label. Nothing else used the old table. The Projects v2 Priority field is
  derived from the issue's labels (`infer_item_priority`), so it follows the corrected label.
- [x] **Roadmap updated**: the Roadmap Deferrals entry no longer lists the priority fix or its
  old mismatch counts, and the upstream survey extension points here.
- [x] **Automated Tests & Quality Gates** (`tests/test_github_roadmap_sync.py`):
  - `test_extract_priority_and_derive_scope` expects tag-based priorities: a P1 item with
    "Blocker" in its title and "critical" in its body, `(P0 - High)` after the bold, a tag
    inside the bold with `, Issue #N`, a tag followed by `(Issue #5)` or with a nested
    parenthetical, a P3 tag on a completed item, tag-shaped title words, a tag in the
    description only, and an untagged header.
  - `test_extract_roadmap_items_live_file_priorities_match_tags` asserts that every open item
    in `docs/ROADMAP.md` has exactly one tag and derives that priority. It failed on the old
    parser with the 19 mislabelled items.
  - Against the live roadmap: 189 open items, 0 mismatches, 0 untagged.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).
