# Proposal: #4956

## Why

The command citation gate of `devops roadmap stage` (#3302, #4197) reads a `devops` command that a plan cites in a sentence with no code span. It took every word after `uv run devops` to the end of the sentence, and all of a text that starts with `devops `, as arguments of the command. The resolver then refused the English words as an unknown command or an unexpected extra argument, so the gate refused good plans. The replay of the recorded plans shows this false refusal in 7 plans (cases 2152, 2175, 2258, 2260, 2524, 2946 and 3183). Closes #4956.

## What Changes

- `cited_command_length` in `src/devops_cli/core/command_resolver.py` walks the words after `devops` through the command tree. The cited command ends at the first word that the command tree does not take: the tree takes an option, the values of a known option, a subcommand name and the declared arguments of the command. A group that needs a subcommand keeps the next word as its subcommand, so the resolver still reports an unknown subcommand. A word before an option stays, because a sentence puts no option after an English word, so the resolver still reports an unknown subcommand before an option, also under a group that runs with no subcommand.
- `command_citation_problems` in `src/devops_cli/roadmap/stage/stage_commands.py` cuts each command that a sentence cites with `cited_command_length` and checks each cited command of a sentence on its own. A code span keeps the full check of all its words.

## Capabilities

- `roadmap-stage/claims`: a command cited in a sentence ends at the first word that the command tree does not take, and keeps its subcommand and a word before an option.

## Impact

- The citation gate stops the false refusal of the 7 recorded plans. It still refuses an unknown option and an unknown subcommand in a sentence, and every problem of a code span: the per-case replay keeps the citation refusals of cases 2130, 2258, 2260 and 3205 and drops the other 5 cases.
- In a sentence, the gate still refuses an unknown subcommand before an option, such as `uv run devops ai ast-graph --help` (the scenario of #3302) and `uv run devops review scan --help` (case 2130), and an unknown option after an argument or an option value, such as `uv run devops pr monitor 4982 --bogus`. A sweep of the command tree cites each of the 505 commands that can run in a sentence, with its arguments, a known option and its value, and then prose. The sweep gives no refusal. With an unknown option before the prose, it gives a refusal for each command except `devops gh api` and `devops uv run`, which send an unknown option on to the tool that they run.
- `uv run devops roadmap eval stage --replay` gives the same report before and after the change: each gate catches all its known defects, and the 5 good plans pass. Case 2175 is no longer refused, but no gate claims its recorded defects, so no judged defect changes.
- In a sentence, the gate does not refuse an unknown subcommand of a group that runs with no subcommand when an English word comes after it, such as `uv run devops scan gitleak to check`, and it does not check a word after the declared arguments unless an option comes after it. A sentence cannot tell these words from prose. A code span gets that check.

## Feasibility

- `_COMMAND_PROSE_PATTERN` in `src/devops_cli/roadmap/stage/stage_commands.py` on `main` at d64c897e2 is `uv\s+run\s+devops\b[^\n.!?]*`, so the cited command runs to the end of the sentence.
- The new test with the Feasibility sentence of case 2152 fails on `main`: the gate gives `unknown command 'to' under 'devops ci'`. `tests/fixtures/roadmap_eval/stage/2152-the-egress-checks-read-legacy-numeric/plan.json` holds the sentence.
- `devops ci` and 13 other command groups declare `invoke_without_command=True`, so a word after them can be prose. The root `devops` group and the `roadmap` group do not, so a word after them is a subcommand.
- `resolve_devops_argv` reports no missing argument and no missing option value (`_parse` returns no finding for them), so a cut before an argument or a value gives no new refusal.
- The Click metadata gives what a command takes: `params` with `param_type_name` `argument` and `nargs`, and an option's `opts`, `secondary_opts`, `is_flag` and `count`. No command of the tree has an option with more than one value, a count option or a group with arguments. Only `devops gh api` and `devops uv run` accept an unknown option, in a code span too.

## Existing Tool Considered

Click's own parser cannot tell an argument from an English word in a sentence. The change reuses the command resolver and the subcommand lookup of Click (`resolve_command`). No new library. Cost to build: about 200,000 tokens and 3 hours.
