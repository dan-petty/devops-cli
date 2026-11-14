# Design

## Decisions

**The check stays after the merge.** Git's fast-forward merge moves a clone that is behind, and the check finds the clone that is ahead or diverged. A check before the merge would refuse a clone that the merge can move.

**The message names the short hash and the subject.** A person reads the commit in the job log without a second command, and the subject says what the local work is. The short hash is what `git log --oneline` shows.

**The test builds a real repository.** `_move_clone` runs git, so a fake of the process would test the fake. The new module builds two commits in a temporary clone, which costs no network and no fixture of the repository.

## Rejected alternatives

- **A check that reads `git merge-base --is-ancestor`.** It answers the same question with a second process and no more detail.
- **The full hash in the message.** The short hash is what a person reads in `git log --oneline`, and the staged commit is already full.
