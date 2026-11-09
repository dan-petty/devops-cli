# Design

## Decisions

- **Place of the keys.** The two keys sit under `ai`, after `max_retries` and before `tasks`, because they are settings of `AIConfig` and not of a task. The comment above them is the place where a reader learns the decision, the prices and where the prices live.
- **Test of the comment.** The comment test walks back from the line `reference_model:` over the contiguous comment lines. YAML loaders drop comments, so only the text of the file can show them.
- **No price in the template.** The prices are not a setting today. They stay in `pricing_overrides.json` on the volume, and the comment says so.

## Rejected alternatives

- **A second ConfigMap key mounted over `pricing_overrides.json`.** It needs a change to the Deployment, covers the file of the volume, and makes `devops ai cost set-price` fail in the pod. Evidence: the pod mounts the volume `roadmap-service-home` at `/home/devops`, and the file sits in `/home/devops/.data/ai/`.
- **`devops ai cost update-pricing --source <file>` at start.** It writes `pricing_snapshot.json` to the same volume and needs a start step in the Service. #4242 covers a repository-owned price with a setting instead.
- **Build the repository-owned price here.** It needs a new setting, a registry change and generated documents. It is a separate feature, so it is split to #4242.
