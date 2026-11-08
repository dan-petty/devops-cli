# Design

## Decisions

- **Walk `model_fields` in a module of `src/`, and report the dotted path of each unknown key.**: The tests must fail on the base tree, and `devops ci fail-to-pass` overlays the `tests/` tree of the head, so the helper cannot live under `tests/`. A dotted path such as `roadmap.implement.not_a_setting` names the key in a form that an author can search in the example.
- **Go into a value only when the field is a nested model.**: A mapping field such as the ladder (`dict[str, list[str]]`) holds user keys, not field names, so the walk does not read its keys. The validator of the ladder checks them (`_check_ladder`).
- **Render the example with `render_active_devops_configmap` and fake settings.**: The test then walks the same text that a deploy applies, with the `service` section that the deploy sets, and the load by `Settings.model_validate` is the check that `deploy-stack` runs.
- **Keep the live ConfigMap out of the test.**: A test of the repository cannot read the cluster. The rule in the two documents makes the author change the live ConfigMap first, and `deploy-stack` refuses a rendering that does not load.
- **Put the rule in `k8s/README.md` and `docs/ROADMAP_WORKFLOW.md`, and not in the pull request template.**: The body of a pull request becomes the squash message, so a template line would enter the history. The rule asks for a comment on the pull request and a paragraph in the proposal.
- **Pin the phrase in `tests/invariants/`.**: The invariant test fails when a later edit drops the rule from one of the two documents.

## Rejected alternatives

- **Set `extra="forbid"` on the models of `Settings`.**: It changes a public behavior: a config file with an old key then fails to load. `grep -n "extra=" src/devops_cli/config/settings.py` shows 14 models that ignore an unknown key, so the change would break each user file that holds one.
- **Check the live ConfigMap in a test.**: The cluster holds it and git does not, and a test never reaches a cluster.
- **Use `kubeconform` or `kubectl diff`.**: They check the shape of a manifest. The settings are one string in the key `devops-cli.yaml`, so they do not see a key inside it.
- **Add a line to the pull request template.**: The template body becomes the squash message.
