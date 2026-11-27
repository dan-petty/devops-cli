# Design: #7400

## Decisions

### Compute the ids as Grafana does

`grafana_ref_ids` takes the refIds that the targets state, in order, and gives each empty one the first id of A, B, ... Z, AA, AB, ... that no target holds yet. An id that a later target states counts as taken, as in `getNextRefId`, which reads the refIds of all targets of the panel.

## Rejected alternatives

- Drop the duplicate check for targets with no refId: a panel with a stated `A` and an unstated target would still pass, but a later change could leave two stated `A`s unseen. The computed ids keep the check for stated ids (`tests/grafana/test_grafana_dashboards.py`, `test_two_stated_ref_ids_stay_duplicates_next_to_a_target_with_none`).
- Normalize the copy in homelab with the ids: DESIGN.md keeps a dashboard copied from upstream as it is published, and the lint would still be wrong for each other Grafonnet dashboard.
