# Design

## The label families

| Field | Values | Labels |
| :--- | :--- | :--- |
| Status | New, Ready, In Progress, In Review, Blocked | `status/new`, `status/ready`, `status/in-progress`, `status/in-review`, `status/blocked` |
| Priority | P0-Critical, P1-High, P2-Medium, P3-Low | `priority/p0-critical`, `priority/p1-high`, `priority/p2-medium`, `priority/p3-low` |
| Value | High, Medium, Low | `value/high`, `value/medium`, `value/low` |
| Effort | High, Medium, Low | `effort/high`, `effort/medium`, `effort/low` |

A label is the field's name and the value, lower case, with a hyphen for each space. The values keep the names of the board options, so refine, the intake model and the constants keep the words they use.

The repository uses the form `<family>/<value>` already (`type/*`, `scope/*`). The four `priority/p*` labels are in use on 775 issues, and `status/ready`, `status/in-progress`, `status/in-review` and `status/blocked` on 124, so they are kept as they are. `status/new`, `value/*` and `effort/*` are new.

These labels go: `priority/high` and `priority/medium` (3 issues, no description: an older scheme), `status/done` (Done is the closed state), `status/triage` (`status/new` is that state now), and `status/ready-to-merge` (a pull request state that no code reads; the `status/` family is the Item's Status now). `.github/labels.yml` declares the families, and `devops gh labels sync` creates them. The sync deletes no label, so the migration deletes the old labels once.

Rejected:

- **GitLab's scoped form `status::new`.** GitHub gives `::` no meaning: a label is a name, and nothing makes two labels of one scope exclusive. The store makes a family exclusive itself, whatever the separator.
- **Kubernetes' names, such as `priority/critical-urgent`.** They rename labels on 775 issues and the values that refine sorts by, for no gain.
- **A `status/done` label.** No workflow sets a label when an issue closes, as the board's built-in "Item closed" workflow set Done. The issue's state holds it: intake treats a closed issue that is not "not planned" as done, and refine takes only open issues.
- **GitHub issue types and issue fields.** They exist only for organizations, and `dan-petty` is a user.

## What an Item is

An Item is an issue, not a pull request, that holds a `priority/*` label. A Candidate is an open issue that holds none. This keeps the meaning that `CONTEXT.md` gives (an open issue becomes an item when intake places it) and the sets that each job read from the board: intake set Priority last, so the board held the issues that intake placed.

Rejected: **every issue is an Item.** Each Candidate would also be an Item, the items gauge would count every issue that no one triaged, refine would count an untriaged issue as a dependency, and readiness would let a pull request close an issue that intake never saw.

A placement that stops before Priority leaves a Candidate. The next run decides it again, writes only the fields that the issue holds no value for, and posts no second reason comment (it looks for `CONST_ROADMAP_INTAKE_REASON_MARKER`). The board version skipped the duplicate check for such an "unfinished item"; that rule goes, and the check runs again.

## Where the job record goes

The job record moves to a hidden block at the end of the issue body:

```text
<!-- devops-roadmap-record {"Priority": "P2-Medium", "Status": "New"} -->
```

Each `>` in the JSON is written as the escape `\u003e`, so no value can end the comment. Every issue the store returns has the block taken out of its body and read into its job record. A body write puts the issue's current block back, and a field or mark write writes the body with the new block. The refine section is already such a block in the body.

Requests, for a listing of `n` Items and for one field write:

| Option | Listing | Field write |
| :--- | :--- | :--- |
| A block in the issue body | 0 more: the REST issue listing holds each body | 1 read and 1 write: `GET` the issue, then one `PATCH` of `labels` and `body` |
| A comment the job owns | `n` more: one comment listing per Item (775 Items here), or the repository's comment listing, 22 pages of 100 here and growing with every comment | 1 read and 1 write, and the labels in a second write |
| The board's TEXT field (today) | 1 GraphQL page per 100 cards | 1 card read and 2 mutations |

Rejected:

- **A comment the job owns.** The cost per listing is above. It also shows in the timeline and notifies each subscriber at every write.
- **The board's TEXT field.** The App cannot reach the board.
- **A file in the Service's data directory.** A run from a terminal and the Service would keep different records, and ADR 0001 keeps the roadmap's state on GitHub.
- **A record in labels**, such as `job/priority-p2`. It doubles the labels and still cannot hold refine's hashes.

A person can edit or delete the block. A block that is not a JSON object reads as an empty record, with a warning that names the issue, and the next write replaces it. Read as an error, one edit would stop every job of the repository; read as empty, a job only treats its own values as unknown, which never reverts a person's value. The body of an issue can hold 65,536 characters; the block takes a few hundred.

## How a job sees a person's change

The rule of ADR 0002 stays: before a field write, the store reads the issue (`GET`), and when the field's value there differs from the value the store read, and from the value it writes, the write raises `RoadmapItemChangedError` before it changes anything. The value read is the store's own last write of that field, else the value of the Item the caller passes. The job record keeps the last value the store set for each field.

A person who adds a label without removing the job's leaves two labels in the family. The field's value is the label whose value the job record does not name, because the job wrote the other one; with more than one such label, the first in the family's order. So a person's label is the value at the next read, and the job's next write of the field sees the change and refuses.

Rejected: **the actor of each `labeled` event.** The issue events report who set a label (ADR 0003), but a read of each Item's timeline costs one request per Item, and the record already tells the job's value from a person's.

`GitHub` has no conditional write for an issue: a person's edit of the labels or the body between the store's `GET` and its `PATCH` is lost. The window is the time between two requests, and the in-process lock (`_JOB_RECORD_LOCK`) keeps the Service's two lanes out of it.

## The store

`RoadmapStore` keeps the members that refine uses (`item`, `items`, `backlog`, `milestones`, `set_field`, `set_marks`, `comments_on`, `read_issue_body`, `write_issue_body`) and their meaning, so `refine.py` needs no change. `add_item` and `graphql_spend` go, and `item_of(issue)` makes the Item that a Candidate's issue would be, for intake's writes.

The GitHub store reads the REST listing of every issue once for its life (one command or one Service round) and keeps it; its own writes update the kept issues. `items(milestone=...)` and `backlog()` read their filtered listings. No request is a GraphQL request except an issue's timeline (`closures`) and the repository's visibility.

## What else goes

- **`.github/roadmap.toml`.** Its one key named the board. The Service runs on each repository in `service.repos`, and a repository needs no roadmap file. `--ref` stays on intake, which reads `.github/labels.yml` at it, and goes from refine, run and return.
- **The GraphQL spend line and the Service's round pause.** They measured and bounded the board reads (#1125, #1400). A round now sends at most one GraphQL request per intake candidate and one per refine round, and `run_gh` paces them. The Service keeps its generic pause seam (`RoundPause`), with no reader.
- **PR readiness.** The check "the one issue is on the roadmap board" becomes "the one issue holds a `priority/*` label", read in the closing-issues query in place of the issue's project cards. `.github/roadmap.toml` is no longer read.
- **`devops gh project reconcile`.** It counted the open issues with no card as awaiting intake. Intake adds no card, so the line goes. The command, `sync`, the views and the template stay: the owner's board uses them.

## Migration

`.data/agent/scratch/board_to_labels.py` is a scratch script, not product code. For each managed repository it reads the board through the owner's token, and for each open issue on the board it prints the labels that the board's Status, Priority, Value and Effort give, the labels to remove from each family, and the card's `Job record` to move into the record block of the issue body, so refine keeps its marks. It also lists the old labels to delete. Without `--apply` and `--i-am-a-person` it writes nothing; a person runs `devops gh labels sync`, then the writes, when the change merges.
