# Design

## Decisions

- **Count the parses with a profile function.** A context manager in the test module sets `sys.setprofile` for the block and restores the previous profile function after it. On each `return` event of the code object of `MarkdownIt.parse`, it keeps the returned tokens. The real parser runs, and the test calls only the public `split_record`.
- **Test each change of #4445 apart.** The test of a body without the opening text and the test of the batch fail when the early return goes. The test of the token shape fails when the core rule `inline` is on again. Each test also checks the result of `split_record`, so a parse that is cheaper but wrong does not pass.
- **Assert the full token shape.** The test of the `inline` rule compares the type and the `children` of each token of the parse of `Plain text.` and a record block. The empty `children` of the `inline` token is the one field that changes with the rule.

## Rejected alternatives

- **Replace `store._BODY_MARKDOWN` with a counting wrapper (the proposal of #4470).** `docs/TESTING.md` (Doubles): "No test patches a devops-cli module, class, function or attribute". The parser is not an edge, and the profile function gets the same counts.
- **Patch `MarkdownIt.parse` on the class, or use `mocker.spy`.** Both replace an attribute of a library object. `docs/TESTING.md` allows a patch of a stdlib or SDK object only as the fallback of a stdlib edge, and markdown-it is no edge.
- **Read `store._BODY_MARKDOWN.get_active_rules()`.** It reads a private name, which `docs/TESTING.md` does not allow. The tokens that the profile function keeps show the same rule through the public `split_record`.
- **Assert a wall-clock time of the batch.** The time changes with the load of the runner, so the test is flaky, and the project bans upper bounds on elapsed time in `tests/` (ast-grep rule).
