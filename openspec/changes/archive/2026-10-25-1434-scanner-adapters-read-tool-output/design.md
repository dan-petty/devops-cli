# Design

## Gitleaks writes its report on stdout

Gitleaks 8 writes the JSON report only to the path that `--report-path` names. `-` names stdout. The adapter runs `gitleaks dir` for files and `gitleaks git` for the history of a repository, because `detect` is deprecated in favour of these two commands. `--redact` writes `REDACTED` in place of each secret in `Secret` and `Match`. The parser reads neither field, so no finding changes, and no secret reaches a log, a recording or a test fixture.

The base scanner already reads the exit code of Gitleaks correctly when the report is on stdout. A leak exits 1 with a JSON report that holds findings, which reads as a scan that ran. A clean scan exits 0 with `[]`. A Gitleaks error exits 1 with no JSON, which reads as a failed scan.

Rejected: `--exit-code 0`, so that any exit other than 0 means an error. The base scanner then reads a leak the same way, so the flag adds nothing. And the run records of a review would show exit 0 for a leak, which hides what the tool said.

## Popeye runs at a lint level, over the namespace that it gets

`-l warn` is the lint level of Popeye 0.22: it reports warnings and errors. `-s` names resource sections, such as `po,svc`, so `-s error,warn` matched no linter. The adapter passes `-n` when it gets a namespace, and runs over every namespace when it gets none, as `popeye` does.

The report has one section for each linter. Its `issues` maps each resource, `<namespace>/<name>`, to a list of issues. The `group` of an issue names the container when the issue is about one container. It is `__root__` for an issue of the resource itself, and empty for an issue that Popeye measured, such as memory use. `CONST_POPEYE_RESOURCE_GROUPS` holds the two values that name no container. The location of a finding adds the container, so two issues with the same message on two containers of one resource stay two findings.

Rejected: put the container in the title or the description only. The location of a finding is its identity in the review, so the review would merge the two findings.

## Pluto names its target relative to its working directory

Pluto builds `filePath` as its working directory, `/`, and the path that it walked (`CheckForAPIVersion` in `pkg/finder/finder.go` at v5.24.4). An absolute target gives a path that does not exist. A target relative to the working directory gives the path of the manifest, with `..` when the working directory is a scratch directory outside the tree. `os.path.normpath` removes the `..`.

The base scanner gives `build_command` the directory that the command starts in, as the keyword `cwd`. A scan that is not isolated starts in the directory that holds its targets, and an isolated scan starts in its scratch directory, so only the base scanner knows the directory. `build_pluto_cmd` names the target with `os.path.relpath`. The request to the tool executor keeps the absolute targets, so the sandbox binds and the digests of a run do not change.

Rejected: correct `filePath` in the parser, by a search for the target in the string. That is string handling of a path that Pluto built wrong, and it fails when the target is a part of the working directory.

Rejected: an override of `_run_built_command` in the Pluto adapter. It is a private method of the base scanner. The keyword `cwd` makes the directory available to each adapter, and no adapter reads `cwd` or passes its keywords on today.

Rejected: start Pluto in `/`, so that the joined path starts with `//`. POSIX keeps a leading `//`, so `normpath` does not remove it.

## Each parser reads only what its tool writes

The Pluto parser reads `api.kind`, `api.version`, `api.deprecated-in`, `api.removed-in` and `name` without a default. The Popeye parser reads `popeye.sections`, `linter`, `group`, `level` and `message` the same way. A report that lacks one of them raises in the parser, and the base scanner reports a failed scan with the missing key. A finding with an invented kind, API or replacement is worse than no finding, because a person acts on it.

`replacement-api` is empty when Kubernetes has no replacement. The finding then says so, and its fix is to remove the object. The `items` of a Pluto report and the `issues` of a Popeye section are absent or empty when the tool found nothing, so both read as no findings.

Rejected: keep the defaults `Resource`, `v1` and `apps/v1` of the old Pluto parser. They told a person to move a PodSecurityPolicy to `apps/v1`.

## The agent tool of Popeye runs the adapter

`scan_popeye` runs `run_popeye_scan` with the namespace and the workspace as its working directory, and replies through `_scan_reply`, as the other agent scan tools have done since #1435. Its own `popeye` command line goes.

## Out of scope

- kubeconform and Checkov: neither tool is in `tools.lock`, so their adapters cannot be tested on a run recorded at a pinned version (#2214).
- `devops scan secrets --json` and the other scan commands print their progress line on stdout before the JSON (#2216). The test of a found leak reads the reply of the agent tool `scan_gitleaks`, which has no progress line.
