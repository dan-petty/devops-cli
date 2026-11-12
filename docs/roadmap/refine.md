# The refine job

`devops roadmap refine` refines roadmap items to Ready. It is step 2 of [the roadmap workflow](../ROADMAP_WORKFLOW.md). The command help gives a summary only. This page gives the rest. The rules that a test checks are in the specs named at the end of this page.

## What refine writes

Refine uses the code and the documents of the repository. For an item it writes a proposed design, tasks and acceptance criteria. When the item is whole, it sets the Status to Ready.

An item that refine cannot set to Ready gets one comment with its next step. The step is one of these:

- The questions that a person answers.
- The split that a person makes.
- The open items that this item waits on.

A proposal that names an open issue as a dependency is not whole. The item waits on that issue. Refine does not set it to Ready, and a Ready item goes back to New. A closed dependency holds nothing back.

The Dependencies section of the body names an issue as `#N` or by its quoted title, such as `- "feat(roadmap): run each refine item in its own pod".`. Refine adds each issue that the body names by title to the dependencies of the proposal: the one open item with that exact title, else the one closed item with it. Quoted text that is no Conventional Commit title names no issue, and a list item that names `#N` names its issue by the number.

Refine looks at the item again after a reply, a body edit, or the close of those open items. It also looks again after a commit on the default branch that changes a file that the block cites. The report groups every item by its next step.

Refine writes the new body, the job record and the Status of an item with one request. The comment follows as a separate request. A stop after the write leaves the new body and its marks together.

An item that waits on a person has one more way out. The comment of refine names issues and files in its questions. Refine looks at the item again when an issue that the comment names closes after the comment, or when a file that it names changes on the default branch after the comment. A round reads at most 5 issues and 5 files from one comment.

## Items that the stage job returns

The stage job can return an item to New with evidence that the plan cannot hold. That is the act of a job, not of a person, so the next round refines the item again with no reply and no body edit. The model reads the evidence of the return in `stage_return`. A plan pull request that a person closed with no merge is such a return. The stage job copies the reason of the person to the issue and returns the item to New. Then `stage_return` holds that reason. A round that looks at the same body again records its hash in `refine.returned_body_hash`. When the stage job returns the item a second time on that body, refine does not look again. The item waits on a person, and the reason is `devops roadmap explain <number>` and a line in `devops roadmap inbox`. A reply or a body edit ends that wait. A person who sets an item back to New with no comment is the other case: the item waits for the reason of that person.

## Items that a bot opens

The Service App and the workflows of the repository open items. Examples are the parts that refine splits off and the findings of an audit. A round takes an item whose author login is exactly `service.github_app.bot_login` or `github-actions[bot]`. It takes such an item as it takes the item of a person with write access. It takes no item of another bot or of an outside account. Refine writes one comment on such an item to tell its author why the round leaves it alone.

Nobody wrote the text of a bot item, so a Ready proposal for it goes through a review first. The review is the verification pass of the stage job, with the model of the task slot `ai.tasks.verification`. It reads the issue and the proposal. With no open finding, refine sets the item Ready and records `refine.judge` `approved`.

With an open finding, the item stays New and waits for a body edit. One comment lists each finding with its evidence. The approval covers the body that the review read, and the hashes in the job record show it. A body edit ends the approval, and the next round reviews the item again. The stage job, the implement job and the alternatives job take a bot item only with an approval that holds.

The review is a model, so text in the item can mislead it. The control is the login of the author. The models of refine and of the alternatives job read only the replies of two kinds of author. These are a person with write access and the App's bot. A person still merges each pull request. A comment of a bot starts no `implement: retry`.

## What refine investigates

When a fact or a decision has no verified source, or a key question of the body has no answer, refine investigates it. It uses tools that read the code. For a public repository with at least one configured search provider, it also searches the web. The plan says when web search is off. When `crawl4ai.url` is set, the run also has the tool `fetch_page`, which reads the text of one page through the Crawl4AI service. It takes an https URL that a search of the same run returned or that the item text names, and no other URL; it sends no request for any other URL. A run fetches at most 3 pages. The tool frames the text as data from an outside page, never an instruction, and names the source URL and the fetch date so that a comment can cite them. A failed fetch is a tool answer and uses one fetch. Each call counts in `devops_cli_roadmap_page_fetches_total` by `toolset` (`refine` or `alternatives`) and `result` (`ok`, `refused`, `limit` or `error`). The tool is off with no `crawl4ai.url`.

A design question gets the best-practice option, with the options that refine compared. Only a decision that a person must make waits on a person: a question marked `(a person decides)`.

When the investigation ends with no proposal, for example with `Exceeded maximum output retries (2)`, and a question that is not a person's is still open, the round is a job failure (see below). When the stop leaves only person questions and decisions marked `(proposed)`, the first proposal stands.

## Which items refine takes

Without `--item`, refine takes items in this order, nearest place first:

1. The New items of each open milestone, by due date and then by number.
2. The P0 and P1 items of the backlog.
3. The other New items of the backlog.

Inside each place, the order is by priority. Only `--limit` stops a run. The number of Ready items does not stop it.

In each open milestone, and among the P0 and P1 items of the backlog, refine also takes Ready items that it has no record of. It sets one of them back to New when it finds the item not ready.

## Items that wait for a person

Two kinds of item wait for a person. Only `--item` refines them:

- An item that another account opened. The accounts that a round trusts are the owner, a member, a collaborator, the Service App's bot and `github-actions[bot]`.
- An item on which refine wrote 2 comments in the last 24 hours. It takes no place under `--limit` until the older comment is 24 hours old.

`--item` refines an open New or Ready item even when nothing changed since its last round.

## Items with an unlisted title type

Refine does not refine an item whose title type the branch types do not list, such as `security(ssh): ...`, also with `--item`. The stage job cannot take such an item, because its branch has no type. The round makes no model call for the item and does not set it Ready. The report and `devops roadmap explain` give the reason `invalid-title-type`:

- For a type that has a correction, `devops roadmap retitle` writes the corrected title, such as `fix(security): ...`. Refine has nothing to do until then.
- For another type, the retitle job comments on the item, and the item waits on a person to edit the title.

Refine reads the title in each round, so the first round after a title with a listed type refines the item.

## Parts that cannot be built now

A part of an item can be one that nobody can build or decide now. When the rest of the item is Ready, refine moves that part to new issues through intake. Each new issue starts with `Split from #<issue>.`. Refine names the new issues in its Ready comment and records them as `refine.deferred`.

An item that is too big for one pull request still waits for a person to split it.

## Job failures

A person has nothing to do for a failed job. These cases are job failures, not person waits:

- The proposal fails a form check. The checks are `problem_statement`, `existing_tool` and `acceptance_criteria`. A proposal that needs a split has no criterion to check.
- A quoted title in the Dependencies section names no item, or two items (`dependencies`). The error names the title and asks for the issue as `#<number>`.
- A question has no verified source after the investigation (`missing_source`), or a question of the body has no answer (`unanswered_question`).
- The investigation ended with no proposal while such a question is open (`investigation_stopped`).

A job failure writes no body and no comment. The job record shows it:

| Key | Value |
| :--- | :--- |
| `refine.next_step` | `retry` below the limit of tries, then `failed` |
| `refine.tries` | The count of rounds that failed on this body. A body edit starts it at 1 again |
| `refine.failed_check` | The names of the failed checks, comma separated |
| `refine.failure` | The last error, with the calls of the read tools when they found no source |

With the step `retry`, the next round refines the item again. At 3 tries (`CONST_ROADMAP_REFINE_MAX_TRIES`) the step is `failed`: refine sends no model request for the item until a person edits its body, and [the inbox](inbox.md) lists it in the class `failed` with the checks, the count and the last error. A proposal that passes clears the keys. A job failure comes before a question for a person: a proposal that is not valid asks nobody.

A Ready item whose new proposal fails a form check keeps its Status and its old design, because refine writes no body for a job failure. The record shows the failure, and the item has the step `retry` or `failed` like a New item. A Ready item that refine finds not ready, by contrast, goes back to New with a comment.

An item that already waits on a person when this rule starts keeps its recorded wait. Refine reads it again only after a reply, a body edit, a change to an issue or a file that the wait names, or `devops roadmap refine --item <number>`.

The plan report starts with the count of the items that go on without a person: the items that are Ready, blocked or in `retry`.

## Failures

An item whose model call fails is skipped and reported. Refine still refines the other items, and then exits 1.

**Placeholder text.** Each free-text field of the reply is a `ReplyText`. A text such as `x`, `y`, `none`, `probe`, `placeholder` or "Not yet: I need to inspect the repository first." fails the schema. The reply goes back to the model once with the schema report. A second reply with a placeholder is a placeholder failure of the item: refine logs the skip, and it writes no comment, no body and no mark. It asks no person and sets no Status. The round does not fail for it, so a placeholder failure never suspends the refine row of the Service. The next round asks the model again. `suspected_block` is a plain text, because `none` is a valid answer for it.

**Failure class and wait.** For every other failed model call, such as a timeout, a dropped stream or a reply that never fits the schema, refine records three keys in the job record: `refine.failed_at`, `refine.failed_step` (`investigate`) and `refine.failed_class`. The class comes from the type of the error by the one table of the failure taxonomy (`CLASS_BY_EXCEPTION`): a timeout is `provider`, and a reply that never validates is `parser`. The next rounds leave the item out until `refine.failed_at` plus the wait of its class (`RETRY_AFTER`: 1 hour for `provider`, `plan_defect` and `ci_infra`, 6 hours for `parser`). The report and `devops roadmap explain` show it as the step `retry`, with the time after which refine takes the item again. A record with no class, an unknown class or a time that is no time waits as `ci_infra` or for no time, and never raises. A failure that the text of the item caused (a reply that never validates) also records the hash of the body, and a body edit ends its wait. A timeout says nothing about the text, so an edit does not end that wait. A second such failure on the same body settles the item to wait on a body edit and clears the three keys. A round whose model call worked clears them, and `--item` overrules the wait. A placeholder failure records nothing, as above.

The command [`devops roadmap repair`](repair.md) sets back the items that a placeholder reply stalled before this rule.

## Where the rules are

| Topic | Spec |
| :--- | :--- |
| The limit, the cap of comments, the items of an account without write access | [roadmap-refine](../../openspec/specs/roadmap-refine/spec.md) |
| The authors that the jobs trust, the review of a bot item, the replies that the model reads | [roadmap-author-trust](../../openspec/specs/roadmap-author-trust/spec.md) |
| The investigation, the options of a decision, web search | [roadmap-refine](../../openspec/specs/roadmap-refine/spec.md) |
| The next-step comment, the paths of a block, a change that ends a wait | [roadmap-refine](../../openspec/specs/roadmap-refine/spec.md) |
| A deferred part and its filing through intake | [roadmap-refine](../../openspec/specs/roadmap-refine/spec.md) |
| The labels and the record of an item | [roadmap-item-labels](../../openspec/specs/roadmap-item-labels/spec.md) |
