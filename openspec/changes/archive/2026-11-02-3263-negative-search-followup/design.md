# Design

## Decisions

- **The hint is a row of the refusal table.** The table already gives the hint of a refused program, the prompt and the document of the workflow (#3072). The row `!` adds the three texts at once, and the test that each replacement names an allowed program or a tool holds the row (`git`). The shell still refuses `!` (criterion 3 of #3263).
- **The limit counts the words of the search, not the program.** The review reproduced E2BIG at 300000 characters; 100000 ran. The cap is 2000 characters for all words together, far above a real search (a literal, two or three paths and a few options) and far below the argument limit. It sits in `config/constants.py` as a `kept` limit with its reason.
- **A reason shows a word escaped and cut.** `unicode_escape` turns a NUL byte, a line break and a character outside ASCII into a visible escape, and the cut keeps a stop reason small. A stop reason also shows the command cut to the same limit.
- **One reader for the step and the gate.** `read_verification` returns the process to start, with its `negative` flag, or the reason. `commands_failure` calls it, and `verification_problem` is its reason. The three old texts become one message with the reason inside. No test or document keeps the old texts.
- **A path that matches no file passes. This is accepted.** A group that deletes a directory needs `! git grep -n name -- src/old tests/` to pass when `src/old` is gone. The stage job already checks the paths of `verify` against the staged tree at plan time (`stage_paths.py`, place `verify`), so a typo is caught there. A test holds the choice.
- **`-e` and `-E` stay refused.** `-e` takes a value and `-E` makes the literal a regular expression with `|`, and the fixed shape has one plain literal. A group that removes several names needs a way to check them, and that is a change of the shape, so it is a separate issue, not a defect of this one.

## Rejected alternatives

- **A path must exist.** A deleted directory is the normal case of the check.
- **Catch `OSError` for every verification command.** It would hide a failure to start, for programs that have no cap. The cap is on the search, which the step reads itself. The wider crash for another program with a very long argument is not new and is not part of #3263.
- **Show the raw word with `repr`.** `repr` keeps non-ASCII characters, which a terminal or a comment can hide or reorder. `unicode_escape` shows ASCII only.
