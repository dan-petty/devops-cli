# Design

## Decisions

- Put the call form in `_citation`, the one function that `_claimed_path` and `_was_seen` share, so the path of the call form and the path of the space form go through the same `path:line` and `./` rules.
- Take only a call of a name in the stage tool set. Another call, such as `cat("a.py")`, is no claim about the run and stays whole.
- Take the first quoted argument only. A call with a keyword argument or with an unquoted argument is out of scope: the stage prompt asks a plan to cite a path in the form `read_file path`.

## Rejected alternatives

- Parse the span with the Python `ast` module: a citation can be cut or can hold `...`, so the parse fails on valid plans.
- A second function for the call form: it would split the path rules in two places.
