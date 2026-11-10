# Design

## Decisions
- **One command with a kind argument.** `devops ai ask-jev <kind> <question>` maps to one `DecisionRequest` with one question named `answer`. The kinds are those of the System One protocol, so there is no layer to learn.
- **The module checks, the command prints.** `jev_ask.build_jev_request` refuses a bad input, and the dry run calls it too, so a dry run and a real run refuse the same input. The CLI and the MCP tool share the check because the tool is generated from the command.
- **Bounds in the constants module.** `CONST_AI_JEV_ASK_MAX_INPUT_CHARS` (16,000 characters in total), `CONST_AI_JEV_ASK_MAX_OPTIONS` (32) and `CONST_AI_JEV_ASK_MAX_LEVELS` (10). The profile of Jev allows 255 options and 10 levels; the lower option bound keeps a request small.
- **No secret.** Jev is a hosted model (SECURITY.md, item 13), and project text and code may go to it. The module refuses an input that `mask_secrets` would change. No message quotes the input.
- **Typed result.** `JevAnswer` holds the kind, the answer, the probability, the confidence, the score, the probabilities, the model and the token counts. `--json` prints it. The result carries `yes` or `no` for a yes/no at the threshold `CONST_AI_JEV_DEFAULT_BOOLEAN_THRESHOLD`.
- **Light imports.** The enum and the result are in `jev_ask_models.py`, so the command module loads `pydantic_ai` only when it runs.
- **Read-only tool.** The row `("ai", "ask-jev")` has `read_only` true and `format_json` true: the command writes nothing and the tool prints JSON.

## Rejected alternatives
- **A group `devops ai jev` with the command `ask`.** A new group is a decision for a person, and one command needs none.
- **A new helper in `jev.py` for one request.** Another change fixes the route and the client in that file. The module here calls the model directly and the report names the helper to add later.
- **A typed result in the dry run.** The repository prints a request plan for a `request-plan` command. The dry run follows that rule.
