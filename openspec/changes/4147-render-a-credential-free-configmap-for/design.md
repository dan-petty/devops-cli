# Design

## Decisions

- **Reuse `is_secret_parameter_name` and remove the matching keys instead of masking them.**: It is the one tested record of a secret-suggesting name (SECURITY.md rule 12), it covers nested keys, and ADR 0018 control 2 removes the key: a masked value under a credential key still names the setting to the planner.
- **Drop the credential-named keys before the settings validation of the render, with a keyword-only `drop_secret_keys` parameter on the two render functions.**: The render refuses a key that no setting declares at `src/devops_cli/k8s/configmap.py:91:unknown = unknown_setting_keys(written)`, so a template that holds a credential key fails before any drop that runs after the render; the drop goes between the service block and that check.
- **Render the sandbox ConfigMap in `render_active_devops_sandbox_configmap` beside `render_active_devops_configmap`, and call it from both deploy paths.**: One render path keeps the same template and active config, and it meets the --stack devops criterion on a native cluster and on an Argo CD-managed cluster.
- **Put the removal walk in `src/devops_cli/security/sanitizer.py` beside `mask_secret_named_values`.**: The name rule and its walk stay in one module, and the k8s renderer holds no pattern of its own.
- **Check the rendered ConfigMap by parsing it and walking every key at any depth.**: A serialized text scan can match a value and miss a nested key; the parsed walk checks exactly the keys the ConfigMap holds.
- **Apply the sandbox ConfigMap right after devops-cli-config and before the manifests.**: The planner run Job mounts it, so the ConfigMap exists before the pod starts, and the first stdin manifest stays devops-cli-config.
- **Keep the name and the single data key of the rendered ConfigMap, and change no manifest.**: The run Job mounts devops-cli-config-sandbox at /config with DEVOPS_CLI_CONFIG at /config/devops-cli.yaml, so the contract holds with no manifest edit.
- **Export the new renderer from `devops_cli.k8s` beside the sibling renderer.**: The deploy command imports the existing renderer from the package, so one import site keeps both renders together.
- **Leave the two recorded draft diffs of the roadmap eval fixtures that quote the renderer unchanged.**: `tests/fixtures/roadmap_eval/completeness/change-4093-complete/draft.diff` and `tests/fixtures/roadmap_eval/completeness/change-4093-hunk-removed/draft.diff` hold the text as recorded data of another change, and no test imports the renderer from them.
- **Reuse the existing YAML parser, renderer and name rule.**: The repository already holds the renderer and the name rule, so the change adds about 25 lines and no dependency.

## Rejected alternatives

- **A new config-only pattern such as token|password|secret|key.**: A second list drifts from CONST_MCP_SECRET_PARAMETER_WORDS, and a bare `key` matches non-credential names such as `keyring` and `keys`.
- **An explicit allow-list of safe keys.**: It needs an update for each safe key and can omit a setting that the Service needs.
- **Copy every key and rely on the admission policy.**: The admission policy judges the shape of a Job; it cannot remove a key from a ConfigMap that already exists.
- **A new deploy-stack flag.**: It adds a second path for the same stack, and a person must remember it.
- **A manifest file under k8s/devops/.**: It would put the settings of the homelab in git, and `k8s/README.md:610:- Git does not hold the Secrets ([Cluster Secrets](#cluster-secrets)) or ConfigMap `devops-cli-config` ([Homelab Values at Deploy Time](#homelab-values-at-deploy-time)).` records that git holds no such value.
- **Leave the copy to a person.**: The issue removes the manual step, and a hand copy drifts from the active config at the next deploy.
- **A private filter inside the k8s renderer.**: It puts a second copy of the name rule beside the k8s rendering, where the next credential rule would not reach it.
- **Mask the values with mask_secret_named_values and keep the keys.**: ADR 0018 control 2 removes the key; a masked value under a credential key still names the setting to the planner.
- **Drop the credential keys after the render, on its output manifest.**: `src/devops_cli/k8s/configmap.py:91:unknown = unknown_setting_keys(written)` refuses the template before it returns, so a credential key would stop the render and never reach a later drop.
- **Scan the serialized ConfigMap text for credential words.**: It can match a value and miss a nested key.
- **Rely on the admission policy for the test.**: It does not run in the offline unit test, which doubles the process edges and reaches no cluster.
- **Add yq for the key removal.**: It needs a second render step and a new binary in the image, and it still needs the ConfigMap writer; the alternatives check of 2026-11-10 records it as partly covering the need.
- **Add kustomize.**: configMapGenerator builds a ConfigMap from files and literals and cannot remove a selected key.

## Unchanged references

- `tests/fixtures/roadmap_eval/completeness/change-4093-complete/draft.diff` (fixture text): A recorded draft diff of a roadmap eval fixture for another change; it quotes the function name as data and no test imports it.
- `tests/fixtures/roadmap_eval/completeness/change-4093-hunk-removed/draft.diff` (fixture text): A recorded draft diff of a roadmap eval fixture for another change; it quotes the function name as data and no test imports it.

## Security

The rendered sandbox ConfigMap crosses a trust boundary: it leaves the workstation for the cluster as the config that the sandboxed planner run Job reads, so it must hold no credential. A person must confirm two things before a deploy: that a new key of `k8s/devops/configmap.example.yaml` whose name holds no word of CONST_MCP_SECRET_PARAMETER_WORDS still holds no credential, and that the live sandbox ConfigMap holds no credential key after the deploy. The test `tests/k8s/test_k8s_configmap.py` fails if a credential-named key reaches the rendered ConfigMap, and `tests/security/test_secret_redaction.py` fails if the removal walk keeps one.
