# The refine job

`devops roadmap refine` refines roadmap items to Ready. It is step 2 of [the roadmap workflow](../ROADMAP_WORKFLOW.md). The command help gives a summary only. This page gives the rest. The rules that a test checks are in the specs named at the end of this page.

## What refine writes

Refine uses the code and the documents of the repository. For an item it writes a proposed design, tasks and acceptance criteria. When the item is whole, it sets the Status to Ready.

An item that refine cannot set to Ready gets one comment with its next step. The step is one of these:

- The questions that a person answers.
- The split that a person makes.
- The open items that this item waits on.

Refine looks at the item again after a reply, a body edit, or the close of those open items. It also looks again after a commit on the default branch that changes a file that the block cites. The report groups every item by its next step.

An item that waits on a person has one more way out. The comment of refine names issues and files in its questions. Refine looks at the item again when an issue that the comment names closes after the comment, or when a file that it names changes on the default branch after the comment. A round reads at most 5 issues and 5 files from one comment.

## Items that the stage job returns

The stage job can return an item to New with evidence that the plan cannot hold. That is the act of a job, not of a person, so the next round refines the item again with no reply and no body edit. The model reads the evidence of the return in `stage_return`. A round that looks at the same body again records its hash in `refine.returned_body_hash`. When the stage job returns the item a second time on that body, refine does not look again. The item waits on a person, and the reason is `devops roadmap explain <number>` and a line in `devops roadmap inbox`. A reply or a body edit ends that wait. A person who sets an item back to New with no comment is the other case: the item waits for the reason of that person.

## Items that a bot opens

The Service App and the workflows of the repository open items, such as the parts that refine splits off and the findings of an audit. A round takes an item whose author login is exactly `service.github_app.bot_login` or `github-actions[bot]`, as it takes the item of a person with write access. It takes no item of another bot or of an outside account. Refine writes one comment on such an item, so its author knows why the round leaves it alone, and a person with write access refines it with `--item`.

Nobody wrote the text of a bot item, so a Ready proposal for it goes through a review first. The review is the verification pass of the stage job, with the model of the task slot `ai.tasks.verification`. It reads the issue and the proposal. With no open finding, refine sets the item Ready and records `refine.judge` `approved`. With an open finding, the item stays New and waits for a body edit, and one comment lists each finding with its evidence. The review looks again only after the body changes. The stage job, the implement job and the alternatives job take a bot item only with that approval. The review is a model, so text in the item can mislead it. The control is the login of the author, and the model of refine reads only the replies of a person with write access and of the App's bot. A person still merges each pull request, and a comment of a bot starts no `implement: retry`.

## What refine investigates

When a fact or a decision has no verified source, or a key question of the body has no answer, refine investigates it. It uses tools that read the code. For a public repository with a Firecrawl key, it also searches the web. The plan says when web search is off.

A design question gets the best-practice option, with the options that refine compared. Only a decision that a person must make waits on a person.

## Which items refine takes

Without `--item`, refine takes items in this order, nearest place first:

1. The New items of each open milestone, by due date and then by number.
2. The P0 and P1 items of the backlog.
3. The other New items of the backlog.

Inside each place, the order is by priority. Only `--limit` stops a run. The number of Ready items does not stop it.

In each open milestone, and among the P0 and P1 items of the backlog, refine also takes Ready items that it has no record of. It sets one of them back to New when it finds the item not ready.

## Items that wait for a person

Two kinds of item wait for a person. Only `--item` refines them:

- An item that an account other than the owner, a member or a collaborator opened.
- An item on which refine wrote 2 comments in the last 24 hours. It takes no place under `--limit` until the older comment is 24 hours old.

`--item` refines an open New or Ready item even when nothing changed since its last round.

## Parts that cannot be built now

A part of an item can be one that nobody can build or decide now. When the rest of the item is Ready, refine moves that part to new issues through intake. Each new issue starts with `Split from #<issue>.`. Refine names the new issues in its Ready comment and records them as `refine.deferred`.

An item that is too big for one pull request still waits for a person to split it.

## Failures

An item whose model call fails is skipped and reported. Refine still refines the other items, and then exits 1.

**Placeholder text.** Each free-text field of the reply is a `ReplyText`. A text such as `x`, `y`, `none`, `probe`, `placeholder` or "Not yet: I need to inspect the repository first." fails the schema. The reply goes back to the model once with the schema report. A second reply with a placeholder is a placeholder failure of the item: refine logs the skip, and it writes no comment, no body and no mark. It asks no person and sets no Status. The round does not fail for it, so a placeholder failure never suspends the refine row of the Service. The next round asks the model again. `suspected_block` is a plain text, because `none` is a valid answer for it.

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
