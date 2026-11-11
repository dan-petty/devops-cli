# Design

## Decisions

- `docs/SDLC.md` keeps the filing rule, because Phase 1, Roadmap & Backlog Synchronization, owns the rules of a filed candidate. `docs/ROUTINE_TASKS.md` links to it.
- The Nested Time Limits text is an instruction, because a statement that the code holds the nesting is false while #4678 is open. The text names #4678 so that a reader knows the break.
- The tunnel cut is an idle cut, not a total time limit, so the text does not put it in the nesting. The stream and the keepalive keep a long call alive. `k8s/README.md` owns that design, and `ARCHITECTURE.md` links to it.
- The board audit stays as an on-demand task. The roadmap state is in labels, so no Pre-PR step needs the board.

## Rejected alternatives

- Make the gateway timeout shorter than 125 s. Rejected: the gateway timeouts are 1100 s and 1500 s (`k8s/llm/gateway/config.yaml`) for long model calls, and the keepalive already keeps a streamed call alive through the tunnel.
- Delete the board audit. Rejected: `devops gh project audit` and `devops gh views audit` are commands that a person can still run, and the issue asks only that no Pre-PR step reads the board.
- Edit the archived change folder of #4751 to match. Rejected: that folder records what #4772 delivered, and a pull request must not write the archived folder of another issue.
