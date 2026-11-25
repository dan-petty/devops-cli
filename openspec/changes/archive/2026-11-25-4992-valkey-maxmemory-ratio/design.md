# Design

## Decisions

- **Place the ratio check and negative controls in `tests/gate/k8s_checks/valkey_memory.py`.**
  - `docs/TESTING.md` routes committed-manifest invariant checks to `tests/gate/k8s_checks/` so `kubectl kustomize` renders once per process via `tests/gate/k8s_render.py` (`kustomize`) and `tests/gate/runner.py` auto-discovers every `check_*` function via `pkgutil.iter_modules`. Keeping all manifest rendering and negative-control checks in `tests/gate/k8s_checks/valkey_memory.py` avoids adding new config-reading pytest modules banned by `tests/gate/tree_checks/config_reads.toml`.
- **Inspect every Argo CD path Application (`discover_path_applications`).**
  - Using `discover_path_applications(TREE, REPO_ROOT / "k8s" / "argocd" / "apps")` covers `k8s/llm` and every other kustomization in the repository without duplicating render calls.
- **Tokenize both direct `command`/`args` and shell `-c` wrappers.**
  - All three committed Valkey manifests wrap `exec valkey-server ... --maxmemory <val>` in `sh -c '...'`. Splitting shell script tokens with `shlex.split` and isolating command segments separated by `;`, `&&`, `||`, or `|` detects both wrapped and direct `valkey-server` invocations uniformly and supports both `--maxmemory <val>` and `--maxmemory=<val>`.
- **Use exact `Decimal` byte comparison with `1024`-based `kb`/`mb`/`gb` suffixes.**
  - Parsing `kb`/`mb`/`gb` as powers of `1024` (matching `k8s/README.md` reading `1536mb` against `2048Mi` as `3/4`) and comparing `bound_bytes * 4 > limit_bytes * 3` avoids floating-point rounding error at exact three-quarters boundaries (`768mb` vs `1Gi`). Containers running `valkey-server` without `--maxmemory` are ignored.

## Rejected alternatives

- **Editing `k8s/llm/` manifests in this PR**: Blocked by `tests/gate/k8s_checks/environment_freeze.py`; container sizing moved to `#7140` and `dan-petty/homelab#109`.
- **Adding a pytest test reading YAML files directly**: Refused by `tests/gate/tree_checks/config_reads.toml` and misses Kustomize-rendered workloads.
