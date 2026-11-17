# Tasks

## 1. Each OpenSpec run takes a scratch home

- [x] 1.1 Write a failing test: each run of the gate takes its scratch configuration directory as its home, and no run sets `delivery`
  - Verification: `$ uv run pytest tests/openspec/test_openspec_gate.py tests/openspec/test_openspec_tool.py tests/core/test_openspec_command.py -q`
- [x] 1.2 Set `HOME` beside `XDG_CONFIG_HOME` in `isolated_environment`, and remove `delivery` from `CONST_OPENSPEC_ISOLATED_SETTINGS`
  - Verification: `$ uv run pytest tests/openspec/test_openspec_gate.py tests/openspec/test_openspec_tool.py tests/core/test_openspec_command.py -q`

## 2. The gate reads the skill layout of OpenSpec 2

- [x] 2.1 Write a failing test: a tree whose `.claude/skills/openspec-*` are links to the shared copy, with no `.kilocode/skills`, passes the gate
  - Verification: `$ uv run pytest tests/openspec/test_openspec_gate.py -q`
- [x] 2.2 Remove the `.kilocode/skills` globs from the generated files, the documentation inventory, the review routing and the `openspec-gate` hook, and update the scaffold tests to the 2.x layout
  - Verification: `$ uv run pytest tests/openspec/test_openspec_gate.py tests/commands/test_openspec_scaffold.py -q`

## 3. Pin OpenSpec 2.1.0 and commit what it writes

- [x] 3.1 Set 2.1.0 in `tools.lock` and `openspec/package.json`, write `package-lock.json` again with `npm install --package-lock-only --ignore-scripts` and an empty user configuration, and run `npm ci --ignore-scripts` and `npm audit signatures` in a scratch copy
  - Verification: `$ uv run pytest tests/tools_lock tests/commands/test_install_tools.py -q`
- [x] 3.2 Record `skillsScope: project` in `openspec/config.yaml`, re-include the `.claude/skills/openspec-*` links in `.gitignore`, run `uv run devops openspec regenerate` with 2.1.0 on PATH and commit the skills and the removed files
  - Verification: `$ uv run devops openspec check`
- [x] 3.3 Record the runs of OpenSpec again inside pytest with a scratch test marked `live("openspec")`, and say in the fake how 2.x writes the skills
  - Verification: `$ uv run pytest tests/tools_lock/test_openspec_contract.py -q`

## 4. Renovate takes each OpenSpec release at once

- [x] 4.1 Give the `@fission-ai/openspec` package rule `"schedule": ["at any time"]`, and add to its note that the regeneration needs Git and github.com
  - Verification: `$ uv run pre-commit run check-json --files .github/renovate.json`

## 5. Documents

- [x] 5.1 Add the out-of-date facts to the Status History of ADR 0010, and update the runbook in `tools.lock`, the recording note in `tests/support/openspec_recording.py` and the comment of the `openspec-gate` hook
  - Verification: `$ uv run devops ci docs`
