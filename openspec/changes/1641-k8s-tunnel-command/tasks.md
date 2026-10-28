# Tasks

## 1. The tunnel record and the API answer

- [x] Add failing tests: the record of a forward, its liveness by pid and start time, and `api_server_answers` for a 200, a 401 and a refused connection
  - Verification: `uv run devops ci test tests/k8s/test_k8s_tunnel.py`
- [x] Give the port-forward daemon's lock and liveness check as functions, add the tunnel record in `k8s/tunnel.py`, and add `KubernetesService.api_server_answers`
  - Verification: `uv run devops ci test tests/k8s/test_k8s_tunnel.py tests/test_k8s_port_forward_daemon.py`

## 2. The command group

- [x] Add failing CLI tests: an unset `k8s.tunnel_host`, start with the login first and one forward, a second start, `--context`, `--dry-run`, stop, and status
  - Verification: `uv run devops ci test tests/k8s/test_k8s_tunnel.py`
- [x] Add `k8s.tunnel_host`, `DEFAULT_K8S_TUNNEL_PORT`, `KubernetesTunnelError` and `devops k8s tunnel start|stop|status`
  - Verification: `uv run devops ci test tests/k8s/test_k8s_tunnel.py tests/test_config_declarations.py`
- [x] Replace the manual steps in `k8s/README.md` and regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 3. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 1641-k8s-tunnel-command`
- Pending a person: from off the home network, run `devops k8s tunnel start --context`, complete the Access login, then `kubectl --context <cluster>-tunnel get nodes`.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
