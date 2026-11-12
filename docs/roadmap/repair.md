# The repair pass

`devops roadmap repair` sets back the items that a placeholder reply of a model stalled. The command help gives a summary only. This page gives the rest. The rules that a test checks are in the spec named at the end of this page.

## Why the pass exists

Two jobs once took placeholder text from a model as a real result. A placeholder is a text such as `x`, `placeholder`, `probe`, `pending` or "Not yet: I need to inspect the repository first." The jobs now refuse a placeholder (see [the refine page](refine.md)), and the stage job has no path that returns an item. The items that the old behavior stalled stay stalled until a person or this pass sets them back.

## What the pass lists

An item is stalled by one of two causes:

- **A filler return.** The stage job returned the item to New. The newest comment of the stage job is that return, and its evidence is a placeholder. The pass sets the Status to Ready, the Status that the stage job takes.
- **A stub refine block.** Refine stored a placeholder as the problem statement or as the existing-tool answer, and it asked a person to state the problem. The pass writes the body without the refine section and clears the refine block of the job record. The next refine round reads the item as a new item.

A return whose evidence is a real sentence is not listed, even when the sentence says that the premise holds. No deterministic rule tells such evidence from a true finding, so a person sets those items back.

## What the pass leaves

The pass leaves an item when a person set it or answered it:

- The Status label differs from the Status that a job last recorded.
- An agent or a person owns the item (`owner/agent` or `owner/human`), or a runner Job holds it.
- A comment of a person follows the newest comment of the job.
- A person edited the refine section, so its hash differs from the recorded hash.
- The item is closed.

A comment of another roadmap job is no reply. The alternatives check, the intake reason and a retitle often come after the comment of refine, and each holds the marker of its job. The pass reads past them to the newest comment of the job that stalled the item.

## What the pass reads and writes

Without a flag, the command reads GitHub and lists the stalled items. It writes nothing. With `--confirm`, it reads each listed item again, leaves an item that changed, and writes the rest. An item that fails does not stop the others. A rate limit stops the pass.

A run sends these requests:

| Read | Requests |
| :--- | :--- |
| The open issues | One for each 100 |
| The comments of an item whose record names the next step `ready` or `person` | One for each such item |
| An item that `--confirm` is about to write | One |

`--dry-run` makes no request and lists the reads and the writes. The pass calls no model.

## Where the rules are

[roadmap-repair](../../openspec/specs/roadmap-repair/spec.md) holds the causes, the items the pass leaves, and the writes of `--confirm`.
