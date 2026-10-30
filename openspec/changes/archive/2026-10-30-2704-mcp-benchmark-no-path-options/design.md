# Design

## Decisions

- **The tool publishes none of `output`, `document` and `code`.** Each one names a path on the host. `output` makes the command write a file, and the other two make it read a file or a tree and send the text to a model server. A model must not choose either. `SECURITY.md` principle 11 stated the rule for a URL. The same reasoning holds for a path, so principle 11 now names a path that a model gives: a tool publishes no option for it unless a path helper confines it.
- **An allow list, not a deny list.** The entry of `("ai", "benchmark")` lists the options that stay. A new option of the command is not published until a person adds it (#2480).
- **The tool needs none of the three.** The report comes back on stdout. The embedding benchmark has a built-in corpus. See `proposal.md`, Feasibility.
- **The command keeps the three options.** A person types the paths, so no model sits between the person and the option.
- **The help text of `--samples` names no flag.** The text said "code chunks with --code", and the tool does not publish `code`. A model that read it called `code=` and got a refusal. The text now holds for the command and for the tool. A contract test in `tests/test_fastmcp_contracts.py` holds that no tool text names a flag that the tool leaves out.
- **The tests call the tool through a FastMCP `Client`.** They are in `tests/test_ai_benchmark_mcp_tool.py`, with the tests of #2638. They give a real directory with a real file and check that the directory is unchanged and that no byte reaches the socket. The tests of `--output`, `--document` and `--code` of the command are in `tests/test_ai_benchmark.py` and `tests/test_embedding_benchmark.py`.

## Rejected alternatives

- **Confine each path to the workspace with `safe_resolve_subpath`.** The helper exists. But a model could still choose any file in the workspace, and the tool would send its text to the model server, so the read vector stays. A write to any workspace path stays too: a model could replace a source file with a report. The tool also has no workspace setting to confine to, and no generated tool uses `safe_resolve_subpath`, so the change would add a new hook to the generator for options that the tool does not need.
- **Keep `output` and drop `document` and `code`.** The tool already returns the report, so the option adds only the write vector.
- **An invariant test that no MCP tool publishes a path option.** Other tools publish path options on purpose, such as `review_path`. An invariant needs an allow list of them, and an allow list is an escape.
