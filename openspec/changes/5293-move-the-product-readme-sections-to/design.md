# Design

## Decisions

- **One document, `docs/CLUSTER.md`.** The three sections tell how devops-cli runs in a cluster, and the alert descriptions name one document. One document keeps each pointer short: `(docs/CLUSTER.md, Roadmap service)`. The title is "devops-cli in the cluster", the title of the old section.
- **The text moves with no change, one heading level higher.** The old `###` sections become `##` sections, and the old `####` subsections become `###` subsections. A heading keeps its text, so each anchor stays the same (`#roadmap-service`, `#go-live-check`, `#crawl4ai`). Only the links change: a link to `../docs/` drops that prefix, and a link or a prose pointer to an environment section (Cluster Secrets, Receiver, LLM Gateway, Pausing an Application) links `k8s/README.md`.
- **"Agent sessions" stays in `k8s/README.md`.** It was a subsection of "devops-cli in the cluster", but it tells about `k8s/agents/`, which the plan of #5120 copies to the environment repository. The issue keeps the environment sections in `k8s/README.md`.
- **A second route for the step.** The route of `k8s/**` to `k8s/README.md` keeps "Stacks Overview" and "Directory Structure". A new route of `k8s/**` gives "Image Pins" of `docs/CLUSTER.md`, so a step that changes a manifest still reads the rule of the image pins. When the environment files leave devops-cli, the new route stays.
- **The row of `AGENTS.md` links the new document.** `test_each_route_names_a_row_of_the_where_to_look_table_that_links_its_document` requires it. `AGENTS.md` had 6,499 of its 6,500 characters (`CONST_AGENTS_MD_MAX_CHARS`). The row uses short link texts (`[k8s]`, `[cluster]`, `[tf]`), and the row of the roadmap workflow uses `[roadmap]`, as the row of the CLI reference uses `[commands]`. The file has 6,490 characters after the change. A decision model (`devops ai ask-jev`, choice, A=0.84) picked this design over the two alternatives below.
- **Records stay as they are.** The archived changes, `CHANGELOG.md` and the recorded evaluation fixtures under `tests/fixtures/roadmap_eval/` tell what was true when they were written.
- **Proof of the k8s change.** `kubectl kustomize` of `k8s/devops`, `k8s/overlays/homelab/devops` and `k8s/monitoring` gives the same bytes at `origin/main` and on the branch. `helm template` of chart `prometheus` 29.47.2 with the values file gives 69 rules on both, and 21 rules differ only in `annotations.description`, where `k8s/README.md` becomes `docs/CLUSTER.md`.

## Rejected alternatives

- **Drop "Image Pins" from the route and add no route.** It keeps `AGENTS.md` as it is, but a step that changes a manifest no longer reads the rule of the image pins, and the issue asks to re-point the route.
- **Route `k8s/**` to the section "The Image Pins" of `docs/SDLC.md`.** That section tells the same check, and the row "take an issue to release, or a pull request to merge" links `docs/SDLC.md`. But the route then names a row that does not tell about a manifest, and the moved section "Image Pins" gets no route.
- **One document for each section.** Three documents make three pointer forms in the alert descriptions and three entries in the nav, for text that one reader reads together.
- **A pointer section in `k8s/README.md` at the old place.** It is a shim that the project does not keep before `1.0.0`. The row `all` of the stacks table and each re-pointed reference link the new document.
