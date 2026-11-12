# Design

## Decisions

- A command cited in a sentence ends at the first word that the command tree does not list as an option or a subcommand name. The walk looks up names with `resolve_command` on a context parsed from no word, so no command callback starts.
- A group that needs a subcommand keeps the next word, known or not, so `uv run devops roadmap follow 3076` is still refused. A group with `invoke_without_command=True` and a command with no subcommands end before the word, so `uv run devops ci to confirm ...` is accepted.
- A word that starts with `-` stays in the command, so an unknown option in a sentence is still refused (`uv run devops ssh list --dry-run`, cases 2258 and 2260).
- Each `uv run devops` of a sentence starts a new command, and a sentence or a line ends it. Before, the first command took the next commands as its arguments.
- A code span keeps the full check: it marks where its command ends.

## Rejected alternatives

- Check only the commands in code spans: simpler, but it drops the true refusals of an unknown option in a sentence (cases 2258 and 2260).
- Cut a sentence at the first word that the resolver refuses: the resolver names the refused word but not its place, and the parse of Click takes options after English words, so the cut would not be exact.
