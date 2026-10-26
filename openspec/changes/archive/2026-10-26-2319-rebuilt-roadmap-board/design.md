# Design

## What moves

Only open issues move. A closed issue has no work to place, and intake reads only open issues, so a closed card stays on board 2 and goes with it. The 372 archived pull request cards go with board 2 for the same reason: the roadmap jobs read no archived card, and a pull request is not an Item.

The values that move are the five fields the roadmap jobs read and write: Status, Priority, Value, Effort and Job record. Milestone, Labels, Parent issue and the other fields come from the issue.

The "Roadmap run record" draft moves with its Job record, because the jobs refuse to run without it.

## How the move is made

The new board is a copy of board 2 made by GitHub, so the field and option definitions are the same. A script adds each open issue's card, writes the five values by field and option ID, and then reads both boards again and compares them. A second pass just before the switch adds the issues that opened since the first, removes the cards of the issues that closed, and copies the draft again.

## The switch

`.github/roadmap.toml` is read from the default branch through the contents API, so every runner changes board when the pull request merges. Board 2 receives no write after that. Board 2 is deleted once a round of `devops roadmap run` has finished on the new board.

## Rejected alternatives

- **Wait for GitHub Support.** Support is the only way to remove the link, and it has no time limit. The roadmap jobs fail on every round until then.
- **Skip the 46 issues in intake.** It removes the failed writes but leaves 46 open issues off the board for good, and it adds code to work around a fault in GitHub.
- **Recreate the 46 issues.** The issues keep their numbers in documents, change folders and links. A new number breaks each of them.
- **Close and reopen the issue or the board, or unlink and link the repository.** Close and reopen of the issue and of the board were tried and changed nothing.
- **Delete the card behind the link.** A scan of 60,000 project item IDs near the times of the failed adds found no card of board 2 behind the 149 issues, so there is no card ID to delete.
- **Move closed issues and archived cards.** The roadmap jobs read neither, so moving the 1,200 cards would cost thousands of writes for no reader.
