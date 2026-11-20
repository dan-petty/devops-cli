# Design

## Decisions

- Find a missing required parameter with Click. When the strict `make_context` parse fails with an error that names no option, `_missing_required` runs the option parser of the command on a context parsed from no arguments, as `_gives_action_option` does. For each parameter, `consume_value` takes the value from a word, an environment variable, the default map or the default, and `value_is_missing` decides. The first required parameter with no value is the defect. So the result does not depend on the order in which Click converts the values, and an option is given in each form that Click takes (`-sx`, `--summary=x`, `-s x`).
- Look for a missing parameter before the lenient parse. `make_context` consumes the list that it gets, so `_missing_required` reads its own copy of the words before the lenient parse uses them.
- Report a missing option by its first long name, such as `--summary`, and a missing argument by its name, such as `issue`.
- A placeholder is one word. It fills the argument at its position and never an option, so `devops pr describe <issue>` reports `--summary`.
- A command mention with no token after the command path gives no finding. `_parse` already returns no context and no finding for no words.
- A strict parse that succeeds has no missing parameter, so `_missing_required` runs only on the fallback path.

## Rejected alternatives

- Scan the tokens for each required option by hand. It repeats the parser of Click: it missed `-sx`, it ignored an environment variable and a default, and it read `[OPTIONS]` on one path only.
- Map the `MissingParameter` error of the strict parse only. A conversion error of an earlier placeholder hides it.
- Let a placeholder fill any parameter. A placeholder in an argument position cannot give a named option.
- Report a bare command mention. Prose often names a command with no command line.
