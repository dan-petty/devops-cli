# Design

## Decisions

- **Extract the cited paths and identifiers from the backtick-quoted strings of the issue body: a string with a forward slash is a path, and one without is an identifier.**: The issue body cites code in backticks, and this needs no model call.
- **Run the probes in order: path existence, then identifier definition, then the removal commit for a missing one.**: The removal-commit probe is only needed when the path or identifier is missing, so the order saves commands.
- **Bound the probes at 10 commands per issue and record the probes that the bound skipped.**: The cited examples hold 1 to 4 items, and each item needs at most 3 commands. The bound keeps the probe fast and the acceptance criterion asks for a stated number.
- **Put the probe text in the model input under a `probes` key, and ask `feasibility` to quote it.**: The model can quote the text directly, so the Feasibility section rests on evidence.
- **Signal a false premise with a `premise_failed` field on `StageProposal` that holds the evidence.**: A structured field is easy to check and does not depend on parsing free text.
- **On `premise_failed`, run `devops roadmap return <issue> --comment <evidence> --confirm` and open no pull request.**: AGENTS.md rule 2 asks for the evidence and a stop, and no compensating code.

## Rejected alternatives

- **Ask the model to extract the cited paths and identifiers.**: The model cannot run commands, and a regex over backtick-quoted strings handles the extraction with no model call.
- **Run every probe in parallel.**: The removal-commit probe is only needed when the path or identifier is missing, so parallelism wastes commands against the bound.
- **Open a pull request that notes the false premise.**: AGENTS.md rule 2 says to write no compensating code and to return the item with the evidence.
- **Ask `feasibility` to summarize the probe output.**: A summary can omit the evidence, and the acceptance criterion asks the section to quote the probe output.
