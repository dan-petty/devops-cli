# Proposal

## Why

Issue #2004: `devops roadmap refine` stops its second pass when `refine_ready_target` items are Ready, and it counts these items across the open milestones and the whole backlog. A backlog that holds the target number of Ready items stops each round before the round looks at the backlog's other New items (P2 and P3). On 2026-10-20 the board held 64 Ready items against a `release_cap` of 16, so the second pass did not start, and refine looked at no P2 or P3 item (the comment of 2026-10-20 on #1758). The target came from `release_cap` (#1515), which kept a pool of Ready items for the next release start. ADR 0012 and ADR 0013 removed release starts. A person plans the milestones on the board, and the board shows the number of Ready items.

## What Changes

- Refine counts no Ready items. Without `--item`, a round takes up to `--limit` items in this order: each open milestone's New items and the Ready items that refine has no record of, then the backlog's P0 and P1 items, then the backlog's other New items. Only `--limit` stops a round.
- `.github/roadmap.toml` holds only `board`. The key `refine_ready_target` and its default `DEFAULT_ROADMAP_REFINE_READY_TARGET` are deleted. A file that sets the key fails with a `ConfigurationError` that names it, as a file with any other unknown key does.
- `plan_refine`, `refine_item` and the refine job of `devops roadmap run` take no `config` argument, because refine read only the target from it.
- The help text of `devops roadmap refine` and of the MCP tool `roadmap_refine` gives the new order. The selection, the help text and the configuration keys are observable, so the change carries a spec delta.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `roadmap-refine`: the items that a round of `devops roadmap refine` looks at, their order, and the configuration that the roadmap jobs read.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/roadmap/refine.py` (`select_candidates`, `plan_refine`, `refine_item`), `src/devops_cli/roadmap/run.py` (`_run_refine_adapter`), `src/devops_cli/roadmap/config.py` (`RoadmapConfig`), `src/devops_cli/config/defaults.py`, `src/devops_cli/commands/roadmap.py` and `src/devops_cli/lang/en/help.py`.
- Configuration: `.github/roadmap.toml` loses the comment that named the key.
- Documents: `README.md`, `docs/CLI_REFERENCE.md`, `docs/MCP_TOOLS.md` and `docs/commands/roadmap.md`, regenerated.
- Tests: `tests/test_roadmap_refine.py` and `tests/test_roadmap_config.py`.
- Cost: each hourly round of the Service can ask the model about up to `--limit` (default 3) backlog items. An item that nothing changed since its last round costs no model call (#1539), so these calls stop when each backlog item has had its round.

## Feasibility

- On the base commit `d4d6816c`, `select_candidates` in `src/devops_cli/roadmap/refine.py` has two passes. The first pass takes the open milestones' items and the backlog's P0 and P1 items, and it has no Ready check. The second pass takes the backlog's P2 and P3 New items only while `ready_count + taken < ready_target`, and `ready_count` counts each Ready item in the open milestones and in the backlog.
- The acceptance criterion of #2004 names a New item in an open milestone. On the base, the first pass already took that item. The new test has twelve Ready backlog items, one New item in an open milestone and four New backlog items. On the base it failed: the model got the milestone item and the backlog P1 item, and not the P2 and P3 items. So the defect is in the second pass, as the Problem section of #2004 and the comment of 2026-10-20 on #1758 say. The test checks both places.
- GitHub code search for `refine_ready_target` in the owner's repositories (2026-10-24) found the key only in this repository. The five other repositories that hold `.github/roadmap.toml` do not set it, so its deletion stops no roadmap job.

## Existing Tool Considered

GitHub Projects shows the number of Ready items to the person who plans: a board view that groups or filters by Status gives that number. Refine does not need its own count, and nothing is built. The change deletes the Ready count and the second pass of `select_candidates`, the field `refine_ready_target` of `RoadmapConfig`, `DEFAULT_ROADMAP_REFINE_READY_TARGET`, the `config` arguments of `plan_refine`, `refine_item` and `_run_refine_adapter`, and the tests of the target (`test_backlog_p2_and_p3_wait_for_the_configured_ready_target`, `test_omitted_keys_take_their_defaults` and `test_a_ready_target_below_one_fails_and_names_the_key`).
