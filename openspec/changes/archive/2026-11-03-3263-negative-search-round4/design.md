# Design

## Decisions

- **The rule for a refused command is read first, at the start.** The text of a stop that the step wrote starts with the message, so `\A` is exact. The cause rules search the whole text, which holds the command, and a command can hold any of their words. A rule inside the list would still lose to the rules above it. Rejected: remove the words from the echoed command. The command is what a person needs to read.
- **The output is escaped in `_tail`, not in `stop()`.** `_tail` is the one place where the output of a process becomes text of a reason, for a verification command, a formatter, a git command and a commit. `stop()` also gets reasons that hold markdown the job wrote. A second pass there would escape those too. Each line is escaped alone, so the line breaks of the output stay.
- **A trailing slash means a folder.** `StagedTree.has_folder` is the question. A path with no slash is a file or a folder as before.
- **A word that cannot be an argument is refused in `read_verification`.** That is where the step and the gate meet, so both give the same reason, and the step starts no process.
- **The limit is renamed to the thing it limits.** `CONST_ROADMAP_IMPLEMENT_VERIFY_CHARS` bounds the words of every verification command.

## Rejected alternatives

- **Catch `ValueError` around the process.** The reason would name the exception, not the word. The check before the process gives the reason of the gate too.
- **Neutralise `@octocat` and `#123` in a reason.** The reason is posted in an indented block, where GitHub shows no mention. A change of that block is a separate issue.
