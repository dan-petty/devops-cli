# Proposal: #4788

## Why

PR #4772 merged with three review findings that it did not fix, so three texts on `main` are wrong. One filing rule is in two documents, but each rule must be in one document only. The Nested Time Limits text of `ARCHITECTURE.md` says that the limits nest, but #4678 records a break, and the gateway timeout is longer than the idle cut of the tunnel. `docs/ROUTINE_TASKS.md` says that no step reads the project board, but it keeps a board audit at Pre-PR. Closes #4788.

## What Changes

- `docs/ROUTINE_TASKS.md`, principle 6: remove the copy of the rule "File one candidate at a time…" and link to `docs/SDLC.md`, Phase 1, Roadmap & Backlog Synchronization, which owns it.
- `ARCHITECTURE.md`, Nested Time Limits: write the text as an instruction. Name #4678 as the known break. Say that the idle cut of the tunnel is not a limit that nests, and give the stream-and-keepalive design with a link to `k8s/README.md`.
- `docs/ROUTINE_TASKS.md`: the board audit row and the board audit of the GitHub governance task run on demand only. Remove the `devops gh views audit` step from the Cadence A final stage. The grounding step says that it does not read the board, and the board audit links to `docs/SDLC.md` for the rule.
- The change edits documents only and alters no behavior that a consumer observes, so it has no spec delta.
- The change fits one pull request.

## Capabilities

None. The change edits two documents.

## Impact

- `ARCHITECTURE.md` and `docs/ROUTINE_TASKS.md`. No code, setting, test or dependency changes.
- The archived change folder of #4751 stays as it is. It records what #4772 delivered.

## Feasibility

Each fact was checked on `origin/main` at 84df338e:

- `git grep -n "File one candidate at a time" -- '*.md'` found `docs/SDLC.md` and `docs/ROUTINE_TASKS.md`.
- `src/devops_cli/config/defaults.py` sets `DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS = 30.0` and `DEFAULT_GH_SESSION_READ_TIMEOUT_SECONDS = 60.0`. Issue #4678 is open and records that `resource://gh/issues/status` stops at 30 s, before the 60 s bound of its GitHub read.
- `k8s/README.md` says that the tunnel cuts a request that has no data for 125 s, that the CLI streams each chat call, and that the gateway sends a keepalive into a streamed reply that has no data for 30 s.
- `docs/SDLC.md`, Phase 1, Status Lives on GitHub, says that no roadmap job reads or writes the project board.

## Existing Tool Considered

None applies. The change corrects text in two documents and builds no code. It deletes no internal code.
