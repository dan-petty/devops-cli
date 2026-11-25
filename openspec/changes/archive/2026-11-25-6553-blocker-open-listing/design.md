# Design

## Decisions
- Pass `open_numbers: Collection[int]` to `open_issue_dependencies`. This makes callers pass the listing numbers they hold and removes `store.item` calls.
- In refine, build `open_numbers = frozenset(item.number for item in store.open_items())` once per selection and pass it through `_still_waiting` to `_open_blockers` and `_open_dependencies`.
- `ItemTree` provides `item(number: int) -> Item | None` for tracker expansion, looking up from its cached items without extra reads.
- Blocker lookups test `number in open_numbers`: if not present, the dependency is treated as not open or not an Item.

## Rejected alternatives
- Cache `store.item` result for the round: Rejected because it still makes at least one `gh api` read per blocker on first lookup.
- Optional `open_numbers` with fallback to `store.item`: Rejected because callers could omit it silently and retain the unwanted API requests.
- Read listing inside `open_issue_dependencies`: Rejected because it adds a listing read per call when callers already hold the listing.
