# Proposal

## Why

Issue #1434: three scanner adapters of `src/devops_cli/security/` started their tool with flags that it does not take, or read a report that it does not write. Thus a scan that found something read as a failed scan or as a clean scan.

- **Gitleaks.** `build_gitleaks_cmd` ran `gitleaks detect --report-format json --no-git --source <path>`. Gitleaks 8 writes its report only to `--report-path`, so stdout was empty. A clean file exited 0 with no output, which read as a clean scan by chance. A leak exited 1 with no output, which read as a failed scan: `devops scan secrets` on a directory with a GitHub token said "Gitleaks was not run (Scanner exited with code 1 ... leaks found: 1)" and exited 0. The review and `devops scan report` in CI read the same outcome.
- **Popeye.** `build_popeye_cmd` passed `-s error,warn`. `-s` is `--sections`, a list of resource kinds, so Popeye 0.22.1 matched no linter, exited 1 and printed "no linters matched query". The parser read `sanitizers`, which Popeye 0.22 does not write. `run_popeye_scan` took a namespace and did not pass it. The agent tool `scan_popeye` ran its own `popeye` command and read its text output (#1435).
- **Pluto.** The parser read `api.*` and `filePath`, but it wrote invented values for an empty field: `Resource`, `v1` and `apps/v1`. Thus a removed API with no replacement, such as PodSecurityPolicy, read as one to move to `apps/v1`. Pluto writes `filePath` as its working directory joined to the path it read, so the absolute path that the adapter gave it made a path that does not exist, such as `/tmp/x//tmp/x/deploy.yaml`. The finding named no namespace (#1045).

The kubeconform and Checkov parts of the issue moved to #2214, because neither tool is in `tools.lock`.

## What Changes

- Gitleaks runs `gitleaks dir --report-format json --report-path - --redact <path>`, or `gitleaks git ...` for the history of a repository. The report comes on stdout, and each secret in it reads `REDACTED`. A leak is a finding of a scan that ran.
- Popeye runs `popeye -o json -l warn`, with `-n <namespace>` when it gets one and `--context` as before. The parser reads `popeye.sections`: one finding for each issue, at `k8s:<linter>/<namespace>/<name>`, followed by `/<container>` for an issue of one container. The severity comes from the level of the issue.
- `scan_popeye` runs the Popeye adapter from the workspace and replies with its outcome, as the other agent scan tools do.
- Pluto names its target relative to the directory that it starts in, so `filePath` names the manifest. The base scanner gives `build_command` that directory as `cwd`. The parser reads only what Pluto writes: the finding is at `<manifest>:<Kind>/<namespace>/<name>` (or `<Kind>/<name>`), names the release that deprecated or removed the API, and says when Kubernetes has no replacement API. `manifest_location` of the kube-linter adapter, now public, names the manifest.
- The tests replay runs recorded from the pinned tools: `tests/fixtures/scanner_runs/runs_with_findings.json` holds a Gitleaks run that finds a leak, a Pluto run that finds two removed APIs and a Popeye run at warn level. The contract recording of the clean Gitleaks run is recorded again with the new command.
- The knowledge base pages of Gitleaks and Popeye show the commands that work.
- The commands, their output and the reply of `scan_popeye` are observable behavior, so the change has a spec delta: the new capability `scanner-adapters`, and an ADDED requirement of `agent-scan-tools`.
- The change fits in one pull request.

## Capabilities

### New Capabilities

- `scanner-adapters`: how the Gitleaks, Popeye and Pluto adapters start their tool and read what it writes.

### Modified Capabilities

- `agent-scan-tools`: `scan_popeye` runs the Popeye adapter.

## Impact

- `src/devops_cli/config/commands.py` (`build_gitleaks_cmd`, `build_popeye_cmd`, `build_pluto_cmd`), `src/devops_cli/config/constants.py` (`CONST_POPEYE_RESOURCE_GROUPS`), `src/devops_cli/security/base.py`, `src/devops_cli/security/gitleaks.py`, `src/devops_cli/security/popeye.py`, `src/devops_cli/security/pluto.py`, `src/devops_cli/security/kubelinter.py`, `src/devops_cli/ai/tools/builtin_tools.py`.
- The knowledge base pages `it_domains/tools/gitleaks.md` and `it_domains/tools/kubelinter_popeye_pluto.md`.
- `tests/support/fakes/scanners.py`, `tests/fixtures/scanner_runs/`, and the tests of the adapters, the builders, the agent tools, the tool runs and the scanner contract.

## Feasibility

Each premise was checked against the pinned tool on 2026-10-25:

- Gitleaks 8.30.1: `gitleaks detect --report-format json --no-git --source <dir>` wrote nothing to stdout. `gitleaks dir --report-format json --report-path - --redact <file>` wrote `[]` and exited 0 for a clean file, and wrote a report with `Secret` and `Match` as `REDACTED` and exited 1 for a file with a GitHub token. `devops scan secrets` on that directory said that Gitleaks was not run.
- Popeye 0.22.1 (`popeye --help`): `-l, --lint` is the lint level and `-s, --sections` names resources. `popeye -o json -s error,warn -n default` exited 1 with "no linters matched query". `popeye -o json -l warn -n argocd` on the lab cluster (read-only) wrote `popeye.sections[]` with `linter`, `gvr`, `tally` and `issues`, each issue with `group` (a container, `__root__` or empty), `gvr`, `level` and `message`, and exited 1 because one issue had level 3.
- Pluto 5.24.4: `CheckForAPIVersion` in `pkg/finder/finder.go` of FairwindsOps/pluto at v5.24.4 builds `filePath := fmt.Sprintf("%s/%s", cwd, file)`. From the directory of the manifests, `pluto detect-files -d .` wrote the path of the manifest. With an absolute `-d`, it wrote the working directory joined to that path. From another directory, `-d ../tree/k8s` wrote `<cwd>/../tree/k8s/deploy.yaml`. PodSecurityPolicy `policy/v1beta1` has `replacement-api: ""`. With nothing to report, Pluto wrote JSON with no `items` and exited 0.

## Existing Tool Considered

The tools are Gitleaks, Popeye and Pluto, which `tools.lock` pins. The change uses each tool's own flags and report format, and builds no scanner. The path of a Pluto finding comes from `os.path.relpath` and `os.path.normpath` of the standard library.

The change deletes the parser of the Popeye `sanitizers` report, the invented values of the Pluto parser and the `popeye` command line of `scan_popeye`, and the tests that fed the adapters reports in shapes that the tools do not write.
