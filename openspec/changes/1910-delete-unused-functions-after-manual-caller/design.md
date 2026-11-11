# Design

## Decisions

- **Delete a symbol only when every line that holds its name is its definition or a test.**: search_code reads every file of the commit, so the documents, the knowledge base and the entry points were searched with the same call.
- **Leave the harness slot helpers and the rate limiter module unchanged.**: The refine block of #1910 reserves both files for the items that delete those modules.
- **Delete the test that only exercises a deleted symbol, or its assertions when the test also covers other code.**: A test of deleted code cannot pass, and the rest of a shared test keeps its coverage.
- **Keep the traces command, format_argo_app_status_panel and the name string of argo_app_status.**: They are a registered command and a rendered panel name, so a consumer observes them.
- **Verify a group with a single literal that only the deleted body holds, such as merged_findings or resolve_trace_spans, when the symbol name is a common word.**: A literal with a space is no argument of the git grep form, and a one-word literal such as merge would still match unrelated text of the same file.
- **Add no vulture gate to CI.**: The trial needed 12 decorator patterns and 7 name patterns, and vulture cannot see dynamic use.
- **Carry no spec delta.**: The change deletes uncalled code and changes no command, option, message or service behavior.

## Rejected alternatives

- **Delete every symbol that vulture or the 129-symbol audit lists.**: The issue records at least 26 false positives in the audit, and the search shows that traces is a registered command and argo_app_status a panel name.
- **Add vulture as a CI row.**: The issue records that the trial needed 12 decorator patterns and 7 name patterns before its list was usable.
- **Delete get_last_request_epoch and the three helpers of the harness slots module.**: The refine block of #1910 requires both files unchanged, and find_issues found no open item that names the rate limiter.
- **Search only src and tests for a caller.**: A string, a registry entry or a framework hook in a document or an entry point is a caller, so the search covered every file of the commit.
