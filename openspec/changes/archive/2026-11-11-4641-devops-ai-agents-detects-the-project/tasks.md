# Tasks

## 1. Detected toolchain and checks (behavior)

- [x] 1.1 Write failing tests: a Cargo-only folder, a folder with no manifest and no hooks, several manifests, the devops-cli check line, and the OpenSpec slot
  - Verification: `$ uv run devops ci test tests/commands/test_instruction_generator.py`
- [x] 1.2 Detect the manifests and the plan system, take the checks only from the pre-push hooks, and render the toolchain, rule 4 and the OpenSpec sentence from the detected facts; delete `DEFAULT_AGENTS_MD_CHECK_COMMANDS` and `DEFAULT_PYTHON_REQUIRES`
  - Verification: `$ uv run devops ci test tests/commands/test_instruction_generator.py tests/ci/test_fail_to_pass.py`

## 2. System prompt of the model path (behavior)

- [x] 2.1 Write a failing test: the model call gets no review persona, the checks of the hooks and the detected manifest
  - Verification: `$ uv run devops ci test tests/commands/test_instruction_generator.py`
- [x] 2.2 Send `generate_agents.md` with the detected facts as the system prompt, and put each detected manifest in the project context
  - Verification: `$ uv run devops ci test tests/commands/test_instruction_generator.py`

## 3. Rule titles of the template (behavior)

- [x] 3.1 Write failing tests: the template rule titles match those of `AGENTS.md` less the devops-cli list, and a title added only to `AGENTS.md` is reported
  - Verification: `$ uv run devops ci test tests/invariants/test_agents_md.py`
- [x] 3.2 Give the template rules the titles of the `AGENTS.md` rules
  - Verification: `$ uv run devops ci test tests/invariants/test_agents_md.py`

## 4. Documents

- [x] 4.1 Update the knowledge base guide of the instruction generator
  - Verification: `$ uv run devops ci docs`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
