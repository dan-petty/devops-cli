# Design

## Decisions

- **Create a single shared loader function in review/session.py.**: One place to format the error, one place to test, and the issue identifies the missing loader as the root cause.
- **Raise the project's ValidationError from devops_cli.exceptions.validation rather than a new exception type.**: The verify command already catches this type and exits cleanly; reusing it keeps error handling consistent across review commands.

## Rejected alternatives

- **Add try/except at each of the four call sites.**: Duplicates the formatting logic four times and leaves room for a fifth reader to miss the handler.
