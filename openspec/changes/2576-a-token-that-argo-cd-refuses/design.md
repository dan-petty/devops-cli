# Design

## Decisions

- **Shared helper in argo/credentials.py for the 401 retry logic**: One place for the retry logic, beside the existing token functions. Avoids duplicating the mint-and-retry across four or more commands.
- **Raise ArgoError for all Argo CD API HTTP errors**: ArgoError is a DevOpsCLIError subclass, so the exit seam of new_typer() reports it as one error line with no traceback.
- **Error message names argocd.token and the credential sync command**: Tells the user exactly which keyring entry to fix and which command to run.
- **Helper lives in argo/credentials.py**: Already holds Argo CD credential and token resolution logic. The helper belongs with the code it calls.

## Rejected alternatives

- **Per-command try/except in commands/argo.py**: Duplicates the mint-and-retry logic in every command that calls the Argo CD API.
- **Pre-verify the token in resolve_argocd_server_and_token**: Adds an extra HTTP call to every command. The issue specifies a reactive retry on 401, not a proactive check.
- **typer.Exit(1) for HTTP errors**: Bypasses the exit seam. The user sees no structured error message.
- **A new exception class for Argo CD API errors**: ArgoError already exists in src/devops_cli/exceptions/argo.py and is a DevOpsCLIError subclass.
- **A generic authentication-failed message**: Does not tell the user how to fix the problem.
- **Helper in commands/argo.py**: Mixes command logic with credential logic. The commands should call the helper, not define it.
- **A new module for the helper**: Unnecessary for one function. Adds a file with no other content.
