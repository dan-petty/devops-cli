# Tasks

## 1. Behavior

- [ ] 1.1 A command test shows that `devops roadmap step scaffold` is no command
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_step.py`
- [ ] 1.2 Delete the step, its command, its help text, its record key, `GitHubClient.create_ref` and their tests
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_step.py tests/roadmap/stage tests/invariants/test_roadmap_workflow_doc.py`

## 2. Documents

- [ ] 2.1 Delete the section of the step in `docs/roadmap/stage.md` and its row in `docs/ROADMAP_WORKFLOW.md`, and generate the reference again
  - Verification: `$ uv run devops ci docs`

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
