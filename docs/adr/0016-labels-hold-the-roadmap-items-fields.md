# Labels hold the roadmap Item's fields, and no roadmap job reads or writes a project board

This ADR amends [ADR 0001](0001-github-is-the-roadmap-source.md), [ADR 0002](0002-roadmap-jobs-act-as-a-machine-account.md) and [ADR 0003](0003-polling-is-how-the-roadmap-sees-changes.md).

The roadmap Service acts as a GitHub App that the personal account `dan-petty` owns ([ADR 0015](0015-roadmap-jobs-act-as-a-github-app-on-the-personal-account.md), [#1647](https://github.com/dan-petty/devops-cli/issues/1647)). GitHub gives an App the "Projects" permission only at organization level. So the App cannot read or write a project board that a user owns. Before this decision, each roadmap job needed the board: an Item was an issue with a card, and the card's fields held Status, Priority, Value and Effort. The board's TEXT field `Job record` held the job record, and `.github/roadmap.toml` named the board.

On 2026-10-28 the owner decided that labels and milestones hold an Item's state, and that no roadmap job reads or writes the project board ([#2399](https://github.com/dan-petty/devops-cli/issues/2399)). Private project boards need no support. The owner keeps the board as a personal view, through label and milestone filters.

- **One label family for each field.** A label is the field's name and the value, in lower case, with a hyphen for each space. Status has `status/new`, `status/ready`, `status/planned`, `status/in-progress`, `status/in-review` and `status/blocked`. Priority has `priority/p0-critical`, `priority/p1-high`, `priority/p2-medium` and `priority/p3-low`. Value has `value/high`, `value/medium` and `value/low`, and Effort has `effort/high`, `effort/medium` and `effort/low`. The values keep the names that the board options had. A closed issue is done, so no label holds Done, and a closed issue holds no Status label: the workflow `.github/workflows/clear-status.yml` removes the `status/*` labels when an issue closes (#2717).
- **An Item is an issue with a priority label.** Intake sets Priority last, so an issue with a `priority/*` label is an issue that intake placed, or that a person placed. A Candidate is an open issue with no `priority/*` label.
- **A job replaces the family.** A job sets a field with one `PATCH` of the issue. The `PATCH` removes each label of the family, adds the label of the value, and writes the body with the job record.
- **The job record is a hidden block of the issue body.** The block is `<!-- devops-roadmap-record {...} -->` at the end of the body. The body that the jobs read and write has no block, and a body write keeps the block. A block that is not a JSON object reads as an empty record, and the next write replaces it.
- **A job never reverts a person's change.** The rule of ADR 0002 stays. Before a field write, the store reads the issue. When the field's value differs from the value that the store read, and from the value that the job writes, the write stops before it changes anything. When a family holds two labels, the field's value is the label that the job record does not name.
- **A claim is one more label family (#2910).** Owner has `owner/service`, `owner/agent` and `owner/human`. The label says who works on the Item now, and an Item has at most one. Any actor may claim a free Item: `devops roadmap claim --as agent|human`, and `devops repos worktrees add` for an agent. A person's claim takes an Item from the Service, and the Service takes no Item that an agent or a person holds. The Service claims an Item for the runner Job it creates and releases it when the Job ends. A job replaces the family as it does for every field, so the rule "a job never reverts a person's change" holds for a claim. The close of an issue removes its `owner/*` labels with its `status/*` labels.

## Considered Options

- **The board, through a classic token of a machine account** (ADR 0002): rejected. The service moves to a GitHub App, and an App cannot reach a board that a user owns.
- **A board mirror, or a board fallback**: rejected by the owner. Two stores of one state drift, and the App cannot write the board.
- **GitHub issue types and issue fields**: rejected. They exist only for organizations, and `dan-petty` is a user.
- **GitLab's scoped form `status::new`**: rejected. GitHub gives `::` no meaning, and nothing makes two labels of one scope exclusive. The repository already uses the form `<family>/<value>`.
- **The names of Kubernetes, such as `priority/critical-urgent`**: rejected. They rename the `priority/*` labels on 775 issues and the values that refine sorts by.
- **A `status/done` label**: rejected. The issue's state already holds Done, and a close removes the Status label instead.
- **GitHub assignees, for the owner (#2910)**: rejected. An assignee names a login, and the REST documents describe assignees as people with push access. The three owners are three kinds of actor, and an agent and a person can act as one login. A label family is how this record holds every field, and the poll of ADR 0003 sees a label change.
- **Every issue is an Item**: rejected. Each Candidate would also be an Item, and the items gauge would count each issue that no one triaged.
- **A comment that the job owns, for the job record**: rejected. A read of the Items costs one comment listing for each Item, 775 requests here. The repository's comment listing is 22 pages, and it grows with each comment. A comment also notifies each subscriber at each write.
- **A file in the Service's data directory, for the job record**: rejected. A run from a terminal and the Service keep different records, and ADR 0001 keeps the roadmap's state on GitHub.
- **The actor of each `labeled` event, to see a person's change**: rejected. A read of each Item's timeline costs one request for each Item, and the job record already tells the job's value from a person's.

## Consequences

- The issue listing that the store reads holds each issue's labels and body. So a read of the Items, their fields and their job records costs no request more than the listing.
- A field write costs one read and one write of the issue. GitHub has no conditional write of an issue, so a person's edit between the two requests is lost. In one process, a lock keeps the Service's two lanes out of that window.
- A label change is an issue event with its actor, and the repository webhook sends `labeled` and `unlabeled`. So the poll of ADR 0003 sees a person's change of a field.
- `.github/roadmap.toml`, the board read of the store, the `Job record` field, the board's GraphQL budget probe, the GraphQL spend line of a round and the Service's pause after a board budget refusal are deleted. `devops gh project` keeps its own board reads in `github/project_read.py`, for the owner's board.
- `devops pr check-readiness` blocks a pull request whose one issue holds no `priority/*` label.
- The open issues of each managed repository get their labels from their board values once. A person runs that migration.
