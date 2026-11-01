# Tasks

## 1. Add tests for multi-source repo fallback

Reads: none. Changes: `tests/test_models_argo.py`.

- [x] 1.1 Write three tests: (1) ArgoCDApp.from_api_item with spec.source.repoURL set and spec.sources absent returns that URL; (2) ArgoCDApp.from_api_item with spec.sources as a non-empty list and spec.source absent returns spec.sources[0].repoURL; (3) ArgoCDApp.from_api_item with neither field returns empty string. Repeat the same three for ArgoResourceState.from_manifest, and verify that `uv run devops ci test tests/test_models_argo.py` fails on the base
- [x] 1.2 Add the test functions to tests/test_models_argo.py. Each test builds a minimal dict payload and asserts the repo_url field of the returned model, and verify that `uv run devops ci test tests/test_models_argo.py` passes
- [x] 1.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 2. Add spec.sources fallback to ArgoCDApp and ArgoResourceState

Reads: none. Changes: `src/devops_cli/models/argo.py`.

- [ ] 2.1 The tests from the previous group are the failing tests that this group makes pass, and verify that `uv run devops ci test tests/test_models_argo.py` fails on the base
- [ ] 2.2 In ArgoCDApp.from_api_item, after reading source from spec.get('source', {}), add: if not source.get('repoURL'): sources = spec.get('sources'); if isinstance(sources, list) and sources: source = sources[0] if isinstance(sources[0], dict) else {}. In ArgoResourceState.from_manifest, apply the same fallback after _section(spec, 'source'), and verify that `uv run devops ci test tests/test_models_argo.py` passes
- [ ] 2.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
