# Design

## Decisions

- **A leak marker that no branch name can hold.** The words `secret`, `token` and `user` are usual in branch names, paths and Kubernetes context names. The tracer adds these ambient values to each span, so a scan for usual words depends on the host. The test URLs now hold the marker `..hidden` in each hidden part, and the scan looks for the marker. Git refuses `..` in a ref name, so no branch name can hold it. A URL encoder does not change `.`, so a leak that the code encodes still holds the marker.
- **The scan stays on every attribute.** The test does not list the attributes of the Qdrant client. A new attribute that shows the URL, from the client or from the tracer, makes the test fail.
- **`://` stays in the scan.** Git refuses `:` in a ref name, so the branch name cannot hold `://` either.

## Rejected alternatives

- **Patch `_detect_vcs_metadata` and `_detect_k8s_context` with `monkeypatch`.** The proposed design of the issue named this. `docs/TESTING.md` says that no test patches a devops-cli function and no test imports a private name.
- **Run the test in a fixed checkout under `tmp_path`.** A tree with its own `.git/HEAD` as the current directory, as `tests/support/ci_root.py` does, fixes the branch name. But `_normalize_code_filepath` in `src/devops_cli/telemetry/tracer.py` gives `code.filepath` relative to the current directory only for a file under it. In a tree under `tmp_path`, `code.filepath` becomes the absolute path of `src/devops_cli/ai/rag/qdrant.py`, so a checkout under a path such as `/home/user/` fails the scan for `user`. The fixed checkout also leaves `k8s.context`, which `_detect_k8s_context` reads from `K8S_CONTEXT`. The hermetic floor does not clear that variable.
- **Scan only the attributes that the Qdrant client sets.** The test must then list the attribute keys. An attribute that a later change adds, and that shows the URL, is then not scanned.
