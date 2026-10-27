# Design

The Portkey gateway image `portkeyai/gateway:1.15.0` does not read `/app/config.json`. Self-hosted Portkey gateway receives routing configuration through per-request HTTP headers such as `x-portkey-config`. Therefore, `k8s/llm/portkey/configmap.yaml` is dead configuration.

We remove `k8s/llm/portkey/configmap.yaml` and remove the volume mount from `k8s/llm/portkey/deployment.yaml`. We also remove its path from the Kustomization file and from `stack_lifecycle.py`.

## Rejected alternatives

- **Keep mounting `/app/config.json`**: Leaves dead configuration that misleads operators into thinking the gateway uses it.
- **Convert `/app/config.json` into `./conf.json` with `FETCH_SETTINGS_FROM_FILE=true`**: Portkey `./conf.json` is for admin tokens and provider credentials, not routing fallbacks or model targets.

## Test

Replace `test_portkey_coder_targets_ollama_served_model` in `tests/test_ai_gateway_portkey.py` with an invariant test verifying that `configmap.yaml` does not exist and that the deployment template does not mount or reference `portkey-config`.
