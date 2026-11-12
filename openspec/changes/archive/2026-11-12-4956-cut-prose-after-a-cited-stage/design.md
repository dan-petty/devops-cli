# Design

## Decisions

- A command cited in a sentence ends at the first word that the command tree does not take. The command tree takes an option, the values of a known option, a subcommand name and the declared arguments of the command. The walk reads the names, the arguments (`nargs`) and the option kinds (`opts`, `secondary_opts`, `is_flag`, `count`) from the Click metadata. It looks up a subcommand with `resolve_command` on a context parsed from no word, so no command callback starts.
- A group that needs a subcommand keeps the next word, known or not, so `uv run devops roadmap follow 3076` is still refused. A group with `invoke_without_command=True` and a command with no more arguments end before the word, so `uv run devops ci to confirm ...` is accepted.
- A sentence puts no option after an English word, so a word before an option stays in the command. Under a group that runs with no subcommand, the resolver reports that word as an unknown subcommand: `uv run devops ai ast-graph --help` (the scenario of #3302) and `uv run devops review scan --help` (case 2130) are still refused. Under a command, the resolver reports it as an extra argument, or reports the option after it.
- A word that starts with `-` stays in the command, so an unknown option in a sentence is still refused (`uv run devops ssh list --dry-run`, cases 2258 and 2260). Because the command keeps its declared arguments and the values of its known options, an unknown option after them is refused too: `uv run devops pr monitor 4982 --bogus`, `uv run devops ci fail-to-pass --base origin/main --bogus`.
- A variadic argument keeps one word, and more words only before an option, because a sentence cannot tell its last word from the next English word. A `--` is a dash in a sentence, not an option.
- Each `uv run devops` of a sentence starts a new command, and a sentence or a line ends it. Before, the first command took the next commands as its arguments.
- A code span keeps the full check: it marks where its command ends.

## Limits

- The check does not refuse an unknown subcommand of a group that runs with no subcommand when an English word comes after it, such as `uv run devops scan gitleak to check`. A sentence cannot tell that word from prose. A code span gets that check.

## Rejected alternatives

- Check only the commands in code spans: simpler, but it drops the true refusals of an unknown option in a sentence (cases 2258 and 2260).
- Cut a sentence at the first word that the resolver refuses: the resolver names the refused word but not its place, and the parse of Click takes options after English words, so the cut would not be exact.
- Keep all words up to the last option of the sentence: a sentence can name an option after English words, such as "and check that the plan passes with --dry-run", so this gives false refusals.
