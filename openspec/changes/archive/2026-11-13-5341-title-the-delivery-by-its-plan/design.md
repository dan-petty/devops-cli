# Design

## Decisions

- **The source is the commit that adds the change folder.** The stage job commits the plan with the plan title (`stage.py`, `_git(path, "commit", "-q", "-m", change.title, ...)`), the step `fix-plan` writes it again as one commit with the plan title, and a squash merge writes the title of the plan pull request and the end `(#<pull>)`. So the newest commit of `HEAD` that adds `openspec/changes/<issue>-*/proposal.md` holds the current plan title on a staged branch, on a Planned branch and on the retry of either. The read is local: it sends no request to GitHub.
- **The path glob uses `:(glob)`**, so `*` matches in one folder only, and `<issue>-` with its hyphen does not match a longer issue number.
- **The type and the scope stay the ones of the issue.** The plan title has the type `docs(openspec)`, which the delivery must not keep (#2714). `delivery_title` keeps its scope rule (#2800).
- **The issue summary stands in** when the subject holds no plan title, for example a plan that a person committed with another subject, or when the form refuses the title with the plan summary. The stage schema limits a plan summary to 47 characters, so only a person's longer plan title can be refused. The title of the issue then gives the old behavior, and a title that the form refuses still stops the item.
- **The summary keeps its first letter as the plan wrote it.** The check `Semantic PR title` accepts a capital letter (#4980 had `Fix check-readiness ...`), and a change of case would break a name such as `OpenSpec`.

## Rejected alternatives

- **The first bullet of "What Changes"** (the design of #4127): the bullets are full sentences. For #3785 the first bullet has 169 characters and for #4697 188, over the limit of 60, so the job would fall back to the issue title in the very case of #5341.
- **The title of the plan pull request through `stage.pr`**, as `devops roadmap retitle` does: on a Staged item (#4980) the plan pull request becomes the delivery pull request. After the first write of the delivery title it holds no plan title, so a retry would go back to the issue title. It also costs a GitHub request.
- **A new record key with the plan summary**: the stage job would write it, but the step `fix-plan` and a person's edit of the plan title would not change it, and the items that are staged now have no such key.
- **A model call that writes the title**: the plan already holds a checked summary, and a model call costs tokens and gives a title that no check ties to the plan.
- **A type from the changed paths** (#4127): it is a different decision with its own design, and #5341 asks only for the summary. It stays open in #4127.
