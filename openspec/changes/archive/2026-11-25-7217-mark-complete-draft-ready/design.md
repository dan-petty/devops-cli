# Design

## Decisions

1. **The duty is in rule 6, and the detail is in `CONTRIBUTING.md`.** `AGENTS.md` is near its cap, and it routes "name a branch or a pull request" to `CONTRIBUTING.md`. Rule 6 holds one new sentence. `CONTRIBUTING.md` says what agent work is and which agent marks the pull request ready.
2. **"The checks pass", not "the checks are complete".** The issue quotes the owner direction with "its checks are complete". `devops pr ready` exits 1 for a failed check (`openspec/specs/pr-merge-readiness/spec.md`), and rule 5 says "Pass the checks". The rule names the state in which the command works.
3. **The agent that does the last step marks the pull request ready.** When a second agent checks the report of a builder, that check is agent work. The builder leaves the draft, and the second agent marks it ready after its check.

## Rejected alternatives

- **The sentence "Always mark it ready when all agent work on it is complete and its checks pass." in `AGENTS.md`**: rejected, because the file then has 4,512 characters, and `test_agents_md_stays_within_character_budget` fails at the cap of 4,500 (`CONST_AGENTS_MD_MAX_CHARS`). A higher cap lowers a quality threshold.
- **A `devops pr monitor` that marks the pull request ready when the checks pass**: rejected, because the command reads only GitHub and cannot know that a review or a repair by an agent remains. Bot pull requests have their own row for this step (`openspec/specs/roadmap-stage/ready/spec.md`).
- **A change of Stage 2 in `docs/SDLC.md`**: rejected, because the text there already gives the duty: "Once all work is completed, CI checks pass, and comments are addressed, agents convert the draft pull request to ready for review" (`docs/SDLC.md`, "Two-Stage PR Review Lifecycle").
