# Proposal

## Why

Issue #2572: the Cloudflare tunnel section of `k8s/README.md` writes the public hosts as `*.homelab.<domain>` and `<name>.homelab.<domain>`. The Ingress manifests under `k8s/` serve `<name>.<domain>`. A person who follows the section sets the Cloudflare public hostname and the Access application to a domain that no Ingress serves.

## What Changes

- In the section `## Cloudflare Wildcard Tunnel & Ingress Routing` of `k8s/README.md`, write the wildcard as `*.<domain>` and each host as `<name>.<domain>`. The dashboard step sets the subdomain `*`, not `*.homelab`.
- Add one test to `tests/invariants/test_k8s_manifests.py`. It reads the host names of that section and fails for each name that no host of a manifest under `k8s/` matches.
- Split the host reader `_hosts` of that test file, so that the new test and the existing kustomize test share one reader.
- The change has no spec delta. It changes a document and adds a test, and no `devops` command, option or message, no manifest and no service behavior changes. So `.openspec.yaml` sets `skip_specs: true`.
- The change fits one pull request.

## Acceptance

- "No `homelab.<domain>` host form remains in `k8s/README.md` unless an Ingress in `k8s/` uses it": group 1 (README edit). The only Ingress host with `homelab.` is `homelab.example.com` (an alias of Open WebUI); the section never names it.
- "The test fails on the current text and passes after the fix": group 1 (tasks 1.2 and 1.4).
- Pending a person: the check of the live Cloudflare dashboard. No offline command reads it.

## Impact

- Documents: `k8s/README.md` (lines 1131 to 1223 only).
- Tests: `tests/invariants/test_k8s_manifests.py`.
- Code that the change must keep: the helper `_hosts`, the test `test_kustomize_applies_the_overrides_to_every_host_the_application_renders` and the test `test_readme_lists_the_table` in the same file. The anchor `#cloudflare-wildcard-tunnel--ingress-routing` (linked from line 54 and from `k8s/ingress/ingress-routes.yaml`) stays, so the heading text stays.

## Feasibility

Checked on `origin/main` (00a43ae5) on 2026-11-01.

- The defect is real. `git grep -n -E 'homelab\.<|\*\.homelab' -- k8s/README.md` prints eight lines: 1139, 1156, 1157, 1158, 1159, 1166, 1172 and 1178. The line numbers of the issue (972 to 1010) are out of date: the section now sits at lines 1131 to 1223.
- No Ingress serves the form `<name>.homelab.<domain>`. A script that reads every `kind: Ingress` and `kind: Mattermost` document under `k8s/` finds 24 distinct hosts, all `<name>.example.com`. One of them is `homelab.example.com` (`k8s/ingress/ingress-routes.yaml`, line 35), a second host of Open WebUI. It is not a wildcard, and `*.homelab.<domain>` does not match it.
- The hosts that the section names all exist: `chat`, `ai`, `grafana`, `argocd` and `git` in `k8s/ingress/ingress-routes.yaml`, and `mattermost` in `k8s/mattermost/mattermost.yaml` line 25 (`spec.ingress.host` of a `Mattermost` resource, not an `Ingress`). So the reader of the test must read both kinds. The test file already does it: `_hosts` handles `Ingress`, `IngressRoute` and `Mattermost`.
- The host `k8s.<domain>` (subsection 4 of the section) is a Cloudflare TCP route that `devops cloudflare tunnel sync --service tcp://...` makes. No manifest serves it, so the test stops before subsection 4.
- The text agrees with the code. `CONST_CLOUDFLARE_DEFAULT_SUBDOMAINS` is `("*", "@")` in `src/devops_cli/config/constants.py`, and `_format_subdomain_hostname` in `src/devops_cli/commands/cloudflare.py` turns `*` into `*.{domain}`. So `devops cloudflare tunnel sync` and `devops cloudflare dns sync` make the wildcard `*.<domain>`, not `*.homelab.<domain>`. The Gitea section of the README (line 841) already uses `devops cloudflare access sync --domain '*.<domain>'`. The service URL of step 1, `traefik.kube-system.svc.cluster.local:80`, equals the default of `--service`.
- Nothing newer did or removed the work. `git log -S'.homelab.<domain>' -- k8s/README.md` shows the form since 2026-09-28, and the last commit that touched it is the Mattermost change (#2891). No open plan under `openspec/changes/` edits this section. #2570 edits another part of `k8s/README.md` (Prerequisites).
- The planned reader works. A throwaway script, kept outside git, applied the planned rules to the current text and to the text with `homelab.` removed. Current text: seven names do not match (`*.homelab.<domain>`, `ai.homelab.<domain>`, `argocd.homelab.<domain>`, `chat.homelab.<domain>`, `git.homelab.<domain>`, `grafana.homelab.<domain>`, `mattermost.homelab.<domain>`). Fixed text: no name is unmatched.
- First checks of the implementation: `uv run devops ci test tests/invariants/test_k8s_manifests.py`, `uv run devops ci docs` and `uv run devops openspec check`.

## Existing Tool Considered

None needed. PyYAML and `fnmatch` from the standard library read the manifests and match the wildcard. The change reuses `_hosts` and `yaml_documents` of `tests/invariants/test_k8s_manifests.py`, and it adds no module. The change deletes no code.
