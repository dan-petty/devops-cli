# Design

## Decisions

### Parse each `N to <action>` segment

One regular expression finds each count and its action. It ignores an import segment and the
order of the segments, and a plan with no segment reports zero for each count. The alternative,
`tofu show -json`, reads a saved plan file, not the plan output text that this option accepts, and
the command must send no request.

### Require the file and let Typer refuse a missing path

`--plan-file` is a required `Path` option with `exists=True`, `dir_okay=False` and `readable=True`.
Typer checks the path before the command body, names it in the error and exits 2. A manual
`Path.exists()` check would repeat that check and need its own message.

### Remove the sample plan

The sample filled the absent-file case. With the option required, the command has no input without
it, and the sample was the fake output that the issue reports.

## Rejected alternatives

- **Keep the fixed text match:** it reports 0 for every plan that does not hold the sample counts.
- **Run `tofu show -json`:** it reads a saved plan file, not the plan text, and the command sends
  no request.
- **Check the path in the body:** it repeats Typer's check and needs a new message.
- **Read stdin when the option is absent:** it adds an input mode that the issue does not ask for.
