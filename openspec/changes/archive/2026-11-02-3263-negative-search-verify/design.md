# Design

## Decisions

- **One table, in the shell policy.** `implement_shell_policy.py` already holds the one table of the shell (#3072) and the verification list. The negative search is added there as `read_negative_search` and `verification_problem`. The gate imports them. The step imports the first. Nothing else defines the shape.
- **Prefer the first side of the issue: the step runs the form.** The form is the check of a removed name that `docs/TESTING.md` names, so removing it from the gate would leave a deletion with no command. The step runs it as a fixed shape and not as a shell.
- **Options are an allowlist of letters.** `-n -I -F -i -w -l -c -q` change only what git prints or how a text matches. A word of other letters, a long option, `-e` and `-f` are refused, because each can take a value, read a file, open a program or leave the repository. A combined word such as `-nI` is allowed when every letter is on the list.
- **The literal is plain.** A literal has letters, digits, spaces and the signs `_ . : / = @ + , # % ~ -`, and does not start with `-`. The characters of a shell (the semicolon, the pipe, the ampersand, the redirects, the brackets, the dollar sign, the backtick and the quotes) are not in the set, so a quoted pipe is refused too. This keeps the reason simple: the text is a name.
- **Paths are relative and follow `--`.** The step puts `--` before the paths, so git never reads a path as a revision. A path with `..`, a leading `/` or `-` or a pathspec magic (`:(top)`) is refused. At least one path is needed.
- **Pass on exit 1 only.** `git grep` exits 1 for no match and 128 for an error. A pass on "not 0" would pass on a broken command.
- **The gate asks the policy.** `_verify_problem` keeps the check of the `uv run devops` prefix for the generic problem, and for a command of the project form it asks `verification_problem`. A form that the step refuses gets the reason of the step, in one sentence that names the two forms.
- **The agent's shell is unchanged.** `!` is on no allowlist of the shell, and a test holds it.

## Rejected alternatives

- **Remove the form from the gate.** A deletion would have no command that can run again, and the stage prompt, `docs/TESTING.md` and `openspec/config.yaml` all name this form.
- **Add `!` to the verification programs.** The step would run `argv[1:]` unchecked, and every option of `git` and every program would follow the `!`. The reading of #3263 asks for a fixed shape.
- **Run the command through a shell.** The step never does, and the form needs no shell: the exit code is inverted in the step.
- **Allow `-e`, `-P` or `--` before the literal.** None is needed for a name. The refusal lists the allowed options, so the model has the way to correct a command.
