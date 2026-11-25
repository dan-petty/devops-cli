# Proposal: #6602

## Why
When two items ask the same `covers` question from the alternatives check, `refine` posts the owner-question frame on the older item (`#N`) and posts `OwnerQuestion.link_comment` on the linked item pointing to `#N`. When `refine` re-evaluates the linked item, `covers_question` (`src/devops_cli/roadmap/refine/refine.py`) reads only the linked item's own comments, so a trusted person's reply on `#N` leaves the `covers` question unanswered on the linked item (#6602).

## What Changes
- Add `linked_frame_item` in `src/devops_cli/roadmap/owner_question.py` to parse the frame item number from `OwnerQuestion.link_comment`.
- Add optional `frame_comments` and `actor` parameters to `covers_question` (`src/devops_cli/roadmap/refine/refine.py`), reusing `answer_of` with the `OwnerQuestion` hash so a trusted reply after the shared frame answers the `covers` question while preserving local replies and ignoring bot/job-account replies.
- Pass fetched frame-item comments from `refine_one_item` to `covers_question` when the item's comments hold a link comment for an active `covers` check.
- Add tests in `tests/roadmap/test_roadmap_alternatives.py` and `tests/roadmap/refine/test_roadmap_refine_covers_check.py`.

## Capabilities

### Modified Capabilities
- `roadmap-refine/alternatives`: Read trusted person replies after a shared owner-question frame on the frame item as answers to the linked item's `covers` question.

## Impact
- `src/devops_cli/roadmap/owner_question.py`
- `src/devops_cli/roadmap/refine/refine.py`
- `tests/roadmap/test_roadmap_alternatives.py`
- `tests/roadmap/refine/test_roadmap_refine_covers_check.py`

## Feasibility
Confirmed against `origin/main` (`src/devops_cli/roadmap/refine/refine.py:720-745, 3701-3715` and `src/devops_cli/roadmap/owner_question.py:87-119`).

## Existing Tool Considered
No external tool resolves this repository's `OwnerQuestion.link_comment` frames; reuses `answer_of` in `src/devops_cli/roadmap/owner_question.py` and `trusted_replies` in `src/devops_cli/roadmap/refine/refine.py`. Cost to build and keep: under 6k tokens and ~1 hour.
