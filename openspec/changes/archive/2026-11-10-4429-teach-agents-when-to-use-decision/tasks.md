# Tasks

## 1. Documents

- [x] 1.1 Update rule 13 of `AGENTS.md` and keep the file at or under 6,500 characters
  - Verification: `$ python3 -c "from pathlib import Path; print(len(Path('AGENTS.md').read_text(encoding='utf-8').encode()))"`
- [x] 1.2 Update the `ask-jev` skill in the three trees with the same text
  - Verification: `$ diff .agents/skills/ask-jev/SKILL.md .claude/skills/ask-jev/SKILL.md && diff .agents/skills/ask-jev/SKILL.md .kilocode/skills/ask-jev/SKILL.md`
- [x] 1.3 Update the AI comments of the example configurations
  - Verification: `$ uv run pytest -q tests/docs/test_docs.py::test_config_example_yaml_maps_to_settings_fields_and_validates tests/k8s/test_k8s_configmap_keys.py`

## 2. Checks

- [x] 2.1 Run the invariant tests for `AGENTS.md` and the skills
  - Verification: `$ uv run pytest -q tests/invariants/test_agents_md.py tests/commands/test_openspec_scaffold.py`
- [x] 2.2 Run the OpenSpec gate
  - Verification: `$ PATH="$HOME/.local/bin:$PATH" uv run devops ci --only openspec`
