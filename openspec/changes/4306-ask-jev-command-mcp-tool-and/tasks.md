# Tasks

## 1. Behavior

- [ ] 1.1 Write the failing tests of the command, the module, the tool and the skills
  - Verification: `$ uv run devops ci test tests/commands/test_ai_ask_jev.py tests/ai/mcp/test_ai_ask_jev_tool.py tests/invariants/test_skills.py`
- [ ] 1.2 Add the module `jev_ask`, the command, the exposure row and the messages
  - Verification: `$ uv run devops ci test tests/commands/test_ai_ask_jev.py tests/ai/mcp/test_ai_ask_jev_tool.py`
- [ ] 1.3 Add the skill `ask-jev` to the three roots
  - Verification: `$ uv run devops ci test tests/invariants/test_skills.py`

## 2. Documents

- [ ] 2.1 Regenerate the pages of the commands and the tools
  - Verification: `$ uv run devops docs generate --sync-readme`
