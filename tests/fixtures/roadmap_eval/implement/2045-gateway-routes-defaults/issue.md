## Problem

The gateway router loads a saved route table from `<data dir>/agent/gateway_state.json` in place of `DEFAULT_GATEWAY_ROUTES`, and nothing refreshes that table. So a change to the default routes, such as #1969's move to served models, never reaches a machine that already has the file. On the owner's workstation, the file from 2026-10-22 still holds old vLLM and `ollama.llm.svc` routes.

Found while #1969 was built; its task file names this follow-up.

## Proposed fix

- Keep only the state that failover writes (the `failover:*` routes) in the saved file, and take every other route from the defaults when the router loads.
- Or fold this into the `failover --reset` work of #1986, if that is the smaller change.

## Acceptance criteria

- [ ] A test with a saved file that holds an old default route shows that the router uses the current default.
- [ ] A test shows that a saved `failover:*` route still applies after a restart.
