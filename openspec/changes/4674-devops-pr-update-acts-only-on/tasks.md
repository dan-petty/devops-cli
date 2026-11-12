# Tasks

## 1. Behavior: devops pr update acts only on a failed required check

- [x] 1.1 Write failing tests: a `dirty` pull request gets the rebase steps and no write; a pull request behind `main` with green checks gets no update; a failed required check with no conflict gets one update locked to the head; a failed check that no rule requires gets no update; checks that cannot be read give no update; the command has no `--all`; the dry-run plan names the check reads before the conditional update.
  - Verification: `$ uv run devops ci test tests/commands/test_pr_update.py`
- [x] 1.2 Delete `--all`, `--base` and the bulk loop with their helpers, constant, messages and tests. Read the conflict, the required checks and the check runs before the update, and share `read_required_check_names` with the release pick. Update the MCP tool listing snapshot, and generate the command documents with `devops docs generate --sync-readme`.
  - Verification: `$ uv run devops ci test tests/commands/test_pr_update.py tests/release tests/ai/mcp/test_mcp_tool_listing.py`

## 2. Documents

- [x] 2.1 Add the start, rebase and push lines to the skill `devops-pr-ci` in the three agent roots.
  - Verification: `$ uv run devops ci test tests/invariants/test_skills.py`
- [x] 2.2 Tell in `docs/SDLC.md` (No Catch-Up Updates) what `devops pr update` does.
  - Verification: `$ uv run devops ci docs`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
