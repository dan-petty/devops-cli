# Proposal

## Why

The SARIF export of a review writes no versionControlProvenance. SARIF 2.1.0 requires a repositoryUri in that object (section 3.23.3). The ToolRun record holds the commit but not the repository. A -dirty commit is not a valid revision of the scanned files (section 3.23.4). See #2101.

## What Changes

- Add repository_uri field to ToolRun, read from the remote.origin.url setting of the checkout with the userinfo stripped. A remote that is malformed, or is not an absolute URI with a host, gives None.
- Write versionControlProvenance in the SARIF export. It holds one entry for each distinct pair of repository URI and clean commit among the records of the tool.
- Change the base requirement of sarif-export that forbids versionControlProvenance.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `review-tool-runs`: ToolRun repository_uri field
- `sarif-export`: versionControlProvenance in SARIF export (a MODIFIED requirement)

## Impact

- Code: `src/devops_cli/security/tool_executor.py`, `src/devops_cli/security/sarif.py`
- Tests: `tests/ai/test_tool_executor_contract.py`, `tests/security/test_sarif_emission.py`
- Document: `docs/SELF_IMPROVEMENT.md` (Tool Run Records)

## Feasibility

I ran these commands with git 2.55.0, in a new checkout, in a directory with no checkout and in a directory with an empty `.git` (`git -C <dir> --no-optional-locks <command>`, the form that `_git` uses):

| Command | Case | Result |
| :--- | :--- | :--- |
| `remote get-url origin` | checkout with no remote | exit 2, `error: No such remote 'origin'` |
| `remote get-url origin` | directory with no checkout | exit 128, `fatal: not a git repository` |
| `config --get remote.origin.url` | directory with no checkout | exit 1, no output: git reads the global configuration |
| `config --local --get remote.origin.url` | checkout with no remote | exit 1, no output |
| `config --local --get remote.origin.url` | directory with no checkout | exit 128, `fatal: --local can only be used inside a git repository` |
| `config --local --get remote.origin.url` | directory with an empty `.git` | exit 128, same message |
| `config --local --get remote.origin.url` | remote `https://user:token@example.com/a/b.git` | exit 0, URL with the userinfo |

- `_git` in `src/devops_cli/security/tool_executor.py` raises `SandboxError` when the exit code is not in `accepted`. So the plan reads the remote with `config --local --get remote.origin.url` and accepts exit code 0 and 1. The `git config` manual documents exit code 1 for a key that is not set. The command `remote get-url origin` exits with 2 for a missing remote, and git does not document that code. The option `--local` keeps git from reading the global configuration, and it gives exit 128 for a tree that git cannot read, as the commit read does.
- `_tree_commit` already turns a `SandboxError` into None when `required` is false. `_read_tree_commit` already returns None when `nearest_checkout` finds no checkout. The repository read reuses both guards.
- `urlsplit` gives an empty scheme for `git@example.com:a/b.git` and for `/srv/a.git`, and an empty host for `file:///srv/a.git`. It gives scheme `ssh` and the user name `git` for `ssh://git@example.com/a/b.git`.
- `urlsplit('https://[bad/a.git')` and `urlsplit('https://host]/a.git')` raise `ValueError: Invalid IPv6 URL` (`python3 -I`). So the read catches `ValueError` and gives None.
- `run.versionControlProvenance` is an array with `uniqueItems` in the vendored schema `tests/fixtures/sarif-schema-2.1.0.json`. So one run can hold more than one entry. `repositoryUri` is the only required property of an entry, and it has the format `uri`.
- The tests of `tests/ai/test_tool_executor_contract.py` start git only through the git fake (`_handle_tool_executor_git`). That handler answers `config` with an empty output and exit 0 today, so the handler gets a branch for the new command.

## Existing Tool Considered

The standard library (`urllib.parse`) and the git command cover the need. No other tool is needed. The change extends the existing ToolRun record and SARIF export in src/devops_cli/security/. No internal code is deleted.
