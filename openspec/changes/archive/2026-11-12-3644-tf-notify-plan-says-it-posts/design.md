# Design

## Decisions

- **Change the words, not the behavior.** The command prints the comment and sends no request. The MCP tool is `readOnlyHint: true`, and the design of #3235 records that this issue fixes the words.
- **The invariant reads the dry-run class.** The class `no-external-request` is the declared contract that a command makes no request, so the invariant checks the help of every command of that class, not only `tf notify-plan`. The next command that says "post" and sends nothing fails too.
- **The invariant looks for the verb "post" only.** The probe found "post" only in `tf notify-plan`. Other write words have correct uses in commands of the class: `devcontainer init` names "the published DevOps CLI devcontainer image", and `ssh generate` has a key "Comment".
- **The catalog has no pytest check of its own.** `docs/MCP_TOOLS.md` is generated from the docstring, and the `docs` row of `devops ci` fails when it differs. docs/TESTING.md puts checks of committed files in `devops ci` rows.
- **The help names the sample plan.** The words say what the command does today. Issue #4929 changes the behavior: real counts and an error for a missing file.

## Rejected alternatives

- **Make the command post the comment.** It makes a read-only MCP tool a writer, needs a GitHub client and a token, and contradicts the recorded decision of #3235.
- **Parse the counts and refuse a missing plan file here.** They change behavior that #3644 does not ask for, and the refined design of #3644 keeps them out. Issue #4929 holds them, with `tofu show -json` as the source of the counts.
- **A new file `tests/commands/test_tf_notify_plan_text.py` with a guard for this command only.** docs/TESTING.md puts a new invariant into the file of its subject, and a guard for one command does not find the next one.
