# Roadmap jobs act as a machine account with a classic token

The roadmap jobs change issues and the board with no person present, and reprioritization has to tell a person's change from its own so it never reverts one. They act as a dedicated machine account (GitHub's terms allow one free machine account per person) that holds a classic personal access token with the `project` and `repo` scopes and is invited as a Write collaborator on each managed repository and its board. A GitHub App or a fine-grained token would be the usual choice, but neither can reach a board owned by a personal account; only a classic token can.

## Considered Options

- **The owner's own classic token**: rejected because the jobs' edits would be indistinguishable from the owner's, and both would share one hourly rate limit.
- **Moving the repository and board to an organization so a GitHub App works**: rejected for now because it changes repository URLs and the image path. Revisit if an organization is needed for other reasons; it would also bring issue types and board webhooks.

## Consequences

- GitHub keeps no history of board field changes except Status, so before overwriting a field a job compares it with the value it last set, and leaves it alone if a person changed it since.
