# Proposal: #4306

## Why
An agent has no way to ask TypeSafe Jev (`typesafe/jev-1.14`, the System One decision model) one question. The client in `src/devops_cli/ai/jev.py` serves fixed jobs only: routing, skill choice, tool-call gate, judge and passage filter. The owner asked for an `ask-jev` agent skill and an MCP tool (2026-11-10). Closes #4306.

## What Changes
- Add the command `devops ai ask-jev <kind> <question>`. The kinds are `choice`, `noul` (yes/no) and `score`. It sends one decision request and prints the answer with its probability and the token count. `--json` prints the typed result. `--dry-run` makes no request and prints the request that the real run sends.
- Add the module `src/devops_cli/ai/jev_ask.py`, which builds the request, checks the input and calls the model. It refuses an input of more than `CONST_AI_JEV_ASK_MAX_INPUT_CHARS` characters, and an input that holds a secret. Jev is a hosted model, so the text leaves the cluster. Project text and code may go to Jev (owner policy of 2026-11-10); a secret never does.
- Add the row `("ai", "ask-jev")` to `CONST_MCP_EXPOSURE_TABLE`. The MCP generator makes the read-only tool `ai_ask_jev` from the command.
- Add the skill `ask-jev` to `.claude/skills`, `.agents/skills` and `.kilocode/skills`, and name it in `tests/invariants/test_skills.py` and `CONTRIBUTING.md`.

## Capabilities
- New capability `ai-ask-jev`: the command, the tool and the skill.
- Modified capability `devcontainer-agent-config`: the skill roots hold six skills.

## Impact
- Agents can ask Jev a typed question with one command or one tool call.
- `src/devops_cli/ai/jev.py` is not changed. The change calls `create_jev_model` and the `decide` method of the model. The private helper `_run_decide` of `jev.py` is not imported: a public `decide_with_jev(request, ...)` in `jev.py` would let this module drop its own three-line call.
- The generated pages (`README.md`, `docs/CLI_REFERENCE.md`, `docs/MCP_TOOLS.md`, `docs/commands/ai.md`) list the new command and tool.
- No new dependency, setting or environment variable.

## Feasibility
- `pydantic_ai.models.decision` (the venv source) defines `DecisionRequest`, `ChoiceQuestion`, `NoulQuestion`, `ScoreQuestion` and the matching answers. `SystemOneModel.decide` posts `{state, model, questions}` to `<base>/v1/systemone` and checks each answer against its question. The tests send this wire shape through the HTTP fake.
- The Jev cookbook (https://docs.typesafe.ai/cookbooks) uses the same three question kinds, so the command exposes them as they are.
- `CONST_MCP_EXPOSURE_TABLE` and the generator in `src/devops_cli/ai/mcp/generator.py` already make a tool from each command in the table. So the tool needs no new mechanism. The `--format` and `--json` options leave the tool schema when the table row sets `format_json`, so the tool prints JSON.
- Jev is not reachable live yet: `POST /v1/systemone` gives 404 through the gateway (#4289). The live check waits for that fix. The unit tests prove the command against the wire shape, not against the live service.
- Change from the first design: the command is `devops ai ask-jev`, not `devops ai jev ask`. A group `jev` is a decision for a person (skill `new-scaffold`), and one command needs no group. The tool name follows the command: `ai_ask_jev`. The dry run prints the request plan, as `devops ai fetch-page` does, and not a typed result.

## Existing Tool Considered
`pydantic_ai` `DecisionModel` and `SystemOneModel` are the open tool, and the repository already uses them in `jev.py`. This change adds no client: it adds a thin command, a table row and a skill.
