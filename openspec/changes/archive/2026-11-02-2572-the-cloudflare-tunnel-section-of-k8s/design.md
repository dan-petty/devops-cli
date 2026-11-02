# Design

## Decisions

- **Put the test in `tests/invariants/test_k8s_manifests.py`.** `docs/TESTING.md` (section Layout) names this file as the home of the Kubernetes manifest invariants, and says a new invariant test goes into its subject's file, never into a parallel file. The file already reads the README (`test_readme_lists_the_table`) and the host names of the manifests (`_hosts`).
- **Read the hosts of the manifests, do not list them.** The test takes the hosts of every `Ingress` and `Mattermost` document under `k8s/` through `yaml_documents(K8S_DIR)`. It replaces the placeholder `example.com` with `<domain>`, the form of the README. A new Ingress needs no edit of the test, and a removed host makes the test name the stale README text.
- **Split `_hosts` into `_document_hosts(documents)` and `_hosts(rendered)`.** The new test needs the hosts of parsed documents, and the kustomize test needs the hosts of rendered text. One reader serves both, and its result for the kustomize test does not change.
- **Match with `fnmatch`.** A name of the README matches when `fnmatch.fnmatchcase(host, name)` is true for at least one host. So `*.<domain>` matches every host under the domain, and `*.homelab.<domain>` matches none. A plain name must equal a host. This follows the issue: a `homelab.<domain>` form may stay when an Ingress uses it.
- **Read two kinds of name.** The first kind is every word that ends in `.<domain>`. The second kind is the dashboard bullet `**Subdomain**: ` followed by a code span: the test joins that span and `.<domain>`. Without the second kind, the text `*.homelab` (no `.<domain>` suffix) would pass.
- **Scan the section up to subsection 4.** The text runs from the heading `## Cloudflare Wildcard Tunnel & Ingress Routing` to the heading ``### 4. The Kubernetes API at `k8s.<domain>` ``. Subsection 4 names a Cloudflare TCP route, which no manifest serves. The test fails with a message if either heading is missing, so a rename cannot hide the section.

## Rejected alternatives

- **A new flat file `tests/test_k8s_readme_hosts.py`.** `docs/TESTING.md` forbids a parallel file for an invariant. A flat file under `tests/` also breaks the mirror layout.
- **Assert only that the text `homelab.` is absent.** It misses another wrong form, and it rejects `homelab.example.com`, which an Ingress uses. The issue allows a form that an Ingress uses.
- **List the allowed hosts in the test.** A list drifts from `k8s/`, which is the drift the issue wants to stop.
- **Exempt `k8s.<domain>` in the test.** An exemption hides a name from the check. Scoping the text to the HTTP routes states the real boundary: a TCP route is no Ingress.
