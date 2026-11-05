# Tasks

## 1. An open dependency blocks the item (behavior)

- [x] 1.1 Write the failing test: an open dependency blocks a New item and a Ready item.
  Verification: `uv run devops ci test tests/roadmap/test_roadmap_refine.py`
- [x] 1.2 Write the test: a closed dependency gives the next step `ready`.
  Verification: `uv run devops ci test tests/roadmap/test_roadmap_refine.py`
- [x] 1.3 Write the test: an item with two open dependencies reaches Ready in the round after the last one closes.
  Verification: `uv run devops ci test tests/roadmap/test_roadmap_refine.py`
- [x] 1.4 Add the case of a blocker to the `check_ready` matrix.
  Verification: `uv run devops ci test tests/roadmap/test_roadmap_refine.py`
- [x] 1.5 Read the open dependencies once in `refine_one_item`. Give them to `check_ready` and to `next_step_of`. Remove the store read from `next_step_of`.
  Verification: `uv run devops ci test tests/roadmap/test_roadmap_refine.py`

## 2. Documents (documents)

- [x] 2.1 State in `docs/roadmap/refine.md` that a proposal with an open dependency is not Ready.
  Verification: `uv run devops ci docs`

## Workflow follow-up

- Pending a person: wait until the Service runs the release that holds this change. Then run `devops roadmap refine --item <number> --confirm` once for each Ready item whose Dependencies section names an open issue. Then check each of those items. It must read Status New, `refine.next_step` `blocked` and `refine.blocked_by` set. An item whose new proposal leaves the dependency out stays Ready. The stage job leaves it out as before.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
