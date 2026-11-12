# Tasks

## 1. A command cited in a sentence ends at the first word that the command tree does not list (behavior)

- [x] 1.1 Write failing tests with the sentences of cases 2152 and 2524, a text that starts with a command, and two commands in one sentence. Keep tests that an unknown option and an unknown subcommand in a sentence are still refused.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_command_citations.py`
- [x] 1.2 Add `cited_command_length` to `src/devops_cli/core/command_resolver.py` and cut each command cited in a sentence with it in `src/devops_cli/roadmap/stage/stage_commands.py`.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_command_citations.py tests/core/test_docs_command_resolver.py`
- [x] 1.3 Replay the golden set before and after the change: the citation refusals of cases 2152, 2175, 2524 and 2946 go, and the refusals of an unknown option in cases 2258 and 2260 stay.
  - Verification: `$ uv run devops roadmap eval stage --replay`
- [x] 1.4 Write failing tests for an unknown subcommand before an option (`ai ast-graph --help`, `review scan --help`) and an unknown option after an argument or an option value in a sentence. Keep the declared arguments, the known option values and a word before an option in the cited command.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_command_citations.py tests/core/test_docs_command_resolver.py`

## 2. Documents

- [x] 2.1 Add the requirement of a command cited in a sentence to the `roadmap-stage/claims` spec.
  - Verification: `$ uv run devops ci docs`
