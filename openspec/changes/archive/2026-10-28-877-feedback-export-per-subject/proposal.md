# Proposal

## Why

Issue #877: `devops review export-feedback` writes one record for each copy of a finding in each session. A re-review of one subject, or each run of `devops review benchmark`, writes the same finding again under another session id, because `feedback_fingerprint` holds the session id. The review redesign (#1137, child P2-10) keys the human verdicts and the feedback export by fingerprint v2 (#1141).

The verdicts that a person writes with `devops review verify` are the only labels in the dataset that a person gave. When the sessions of one subject hold different human verdicts, the export must keep each of them, and the newest when two are on one finding.

## What Changes

- The export groups the sessions of one subject by `history.subject_key` (#607). The sessions of one subject share their findings by the fingerprint v2 that admission gives each tool finding (`SavedFinding.fingerprint`).
- Each finding of a subject is exported once, with one verdict:
  - the verdict a person gave it with the newest `verified_at`, from any session of the subject;
  - else the verdict of the session that review history ranks highest among the subject's sessions, which is the session history counts.
- `--status` selects by that verdict, so a verdict that a person later overturned is not exported.
- A session that records no subject (target-only or unkeyed) is a subject of its own, so it exports all its findings. A finding without a fingerprint v2 is matched only in its own session: no title or location match.
- `FeedbackRecord` gains `subject_key` and `fingerprint_v2`. `feedback_fingerprint` identifies a record with a fingerprint v2 by its subject key (or its session id), its fingerprint v2, its status and its labeller. It identifies a record without one by its session, producer, location, title, status and labeller, as before.
- The help of `devops review export-feedback` (and of the MCP tool `review_export_feedback`, which shares it), `docs/SELF_IMPROVEMENT.md` and the code review task of the knowledge base say so.
- The output of `devops review export-feedback` changes, so the change carries a spec delta: the new capability `review-feedback-export`.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `review-feedback-export`: which findings and verdicts `devops review export-feedback` appends to the feedback dataset, and how it counts the sessions of one subject.

## Impact

- `src/devops_cli/ai/review/exporter.py`, `src/devops_cli/commands/review.py`.
- `tests/test_review_exporter.py`.
- `docs/SELF_IMPROVEMENT.md`, `src/devops_cli/ai/knowledge_base/devops_cli/tasks/ai_code_review.md`, and the files that `devops docs generate --sync-readme` rewrites: `docs/CLI_REFERENCE.md`, `docs/MCP_TOOLS.md`, `docs/commands/ai.md`, `docs/commands/review.md`.

## Feasibility

Checked on `origin/main` bb46660c:

- The dependencies are closed as completed: #607 (subject and history), #1141 (fingerprint v2), #871 (admission), #771 (session store) and #1151 (the persona stage is deleted). #608 is closed as not planned.
- `_sanitize_admitted_candidate` (`src/devops_cli/ai/review/pipeline.py:450`) writes the fingerprint v2 of each admitted finding to `SavedFinding.fingerprint`, which `findings.json` and `candidates.json` hold. `history.subject_key` and `load_review_history` give the subject key and the rank of each session.
- `feedback_fingerprint` (`src/devops_cli/ai/review/exporter.py`) held the session id, so three sessions of one subject exported three records of one finding. The new test `test_a_subject_reviewed_three_times_exports_each_finding_once` and six others failed on that code.
- The issue's original design matched findings with `_are_findings_duplicate`. Its 2026-10-08 update replaced that with fingerprint v2, and #1137 keys the export by fingerprint v2. The change follows the update.
- The update also asks that a person's valid verdict set CONFIRMED (`src/devops_cli/review/state.py`). No session file stores a finding's state: `findings.sarif` has no state, and `SavedFinding` has none. To set CONFIRMED needs a place to store it, a rule for a later verdict (`_VALID_TRANSITIONS` lets CONFIRMED move only to FIXED, but a person can change a verdict), and a reader. That is a separate change: #2414.

## Existing Tool Considered

The change uses what the repository already has and builds no new matcher: the fingerprint v2 of admission (#1141) to match findings, `history.subject_key` to group sessions, and `load_review_history` to rank them (#607). No outside tool deduplicates review verdicts across sessions. The change deletes the per-session status filter of `_extract_session_feedback_records`, and the session id as a part of the identity of a finding that has a fingerprint v2.
