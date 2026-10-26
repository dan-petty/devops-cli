# Tasks

## 1. The rebuilt board

- [x] Copy board 2 with `copyProjectV2`, set the copy public, and link it to the repository
  - Verification: `devops gh project list`
- [x] Add a card for each open issue that board 2 held, and copy Status, Priority, Value, Effort and Job record
  - Verification: compare the open-issue cards of both boards with a read of `ProjectV2.items`; no field differs
- [x] Copy the "Roadmap run record" draft with its Job record
  - Verification: compare the draft's fields on both boards; they are equal

## 2. The switch

- [x] Set `board` in `.github/roadmap.toml` to the rebuilt board
  - Verification: `uv run devops roadmap intake --plan --limit 1`

## 3. Verification and static checks

- [x] Verify that the full static checks pass
  - Verification: `uv run devops ci`

## Workflow follow-up

- Pending a person: delete board 2 once a round of `devops roadmap run` has finished on the rebuilt board.
- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).
