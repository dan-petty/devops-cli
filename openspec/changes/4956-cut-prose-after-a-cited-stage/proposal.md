# Proposal: #4956

## Why

The command citation gate of `devops roadmap stage` (#3302, #4197) reads a `devops` command that a plan cites in a sentence with no code span. It took every word after `uv run devops` to the end of the sentence, and all of a text that starts with `devops `, as arguments of the command. The resolver then refused the English words as an unknown command or an unexpected extra argument, so the gate refused good plans. The replay of the recorded plans shows this false refusal in 7 plans (cases 2152, 2175, 2258, 2260, 2524, 2946 and 3183). Closes #4956.

## What Changes

- `cited_command_length` in `src/devops_cli/core/command_resolver.py` walks the words after `devops` through the command tree. The cited command ends at the first word that is no option and no subcommand name. A group that needs a subcommand keeps that word as its subcommand, so the resolver still reports an unknown subcommand.
- `command_citation_problems` in `src/devops_cli/roadmap/stage/stage_commands.py` cuts each command that a sentence cites with `cited_command_length` and checks each cited command of a sentence on its own. A code span keeps the full check of all its words.

## Capabilities

- `roadmap-stage`: a command cited in a sentence ends at the first word that the command tree does not list.

## Impact

- The citation gate stops the false refusal of the 7 recorded plans. It still refuses an unknown option and an unknown subcommand in a sentence, and every problem of a code span: the per-case replay keeps the citation refusals of cases 2130, 2258, 2260 and 3205 and drops the other 5 cases.
- `uv run devops roadmap eval stage --replay` gives the same report before and after the change: each gate catches all its known defects, and the 5 good plans pass. Case 2175 is no longer refused, but no gate claims its recorded defects, so no judged defect changes.
- The gate does not check an argument or an option value in a sentence, because a sentence cannot tell it from the next English word. A code span gets that check.

## Feasibility

- `_COMMAND_PROSE_PATTERN` in `src/devops_cli/roadmap/stage/stage_commands.py` on `main` at d64c897e2 is `uv\s+run\s+devops\b[^\n.!?]*`, so the cited command runs to the end of the sentence.
- The new test with the Feasibility sentence of case 2152 fails on `main`: the gate gives `unknown command 'to' under 'devops ci'`. `tests/fixtures/roadmap_eval/stage/2152-the-egress-checks-read-legacy-numeric/plan.json` holds the sentence.
- `devops ci` and 13 other command groups declare `invoke_without_command=True`, so a word after them can be prose. The root `devops` group and the `roadmap` group do not, so a word after them is a subcommand.
- `resolve_devops_argv` reports no missing argument and no missing option value (`_parse` returns no finding for them), so a cut before an argument or a value gives no new refusal.

## Existing Tool Considered

Click's own parser cannot tell an argument from an English word in a sentence. The change reuses the command resolver and the subcommand lookup of Click (`resolve_command`). No new library. Cost to build: about 200,000 tokens and 3 hours.
