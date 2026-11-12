# Design

## Decisions
- The floor refuses kubectl in each test, its offline renderers included. ADR 0007 (amendment of 2026-10-24) removed this allowance, and `docs/TESTING.md` says that a test of `src/` starts no program. The refusal is the guard: a test that starts a real kubectl fails in the devcontainer and on the GitHub runner too, not only in the runner image. The floor test runs the refusal in an inner pytest run, as the test of the bwrap refusal does, so the case is the same on a host with kubectl and on one without it.
- The image-pin tests answer `kubectl kustomize` from the tree: the resources that the kustomization lists, as one YAML stream. The chart output holds a tab and a lone `=` that PyYAML refuses, so `_chart_answers` also answers the kustomize of the chart output with the committed render, which is the YAML that kustomize writes again. The `image-pins` workflow runs the real tools.
- The gate tests fake the lookup of kubectl on PATH with `monkeypatch`, as `tests/security/test_review_tool_runs.py` does for the scanners. The test of a missing kubectl keeps its own patch of `shutil.which`, which wins inside its block.
- The deploy-stack test checks the shape of the patch: the type is `merge`, and the path `spec.source.kustomize.patches` names no other member. Under RFC 7386 this keeps `kustomize.images`, which is what the real `kubectl patch --local` showed.
- The Qdrant Secret check reads a render of committed manifests, so it goes to the `k8s` row (`tests/gate/k8s_checks/rag_ingest.py`) with `applied_documents`, which shares the one render of `k8s/devops`.

## Rejected alternatives
- `@pytest.mark.live("kubectl")` on the tests that need the binary: `docs/TESTING.md` says that a test must not skip based on host state, and the mark would let each kubectl command of the test start.
- A skip in the floor when kubectl is missing: a second skip path, and it hides the test on the runner where the defect shows.
- Install kubectl in the runner image: #3562 owns that, and it needs a security decision of the owner, because a Job has no cluster token.
- Fake `shutil.which` for all programs in `git_fake`: it changes the lookup for each test that uses git, for a need of one test file.
