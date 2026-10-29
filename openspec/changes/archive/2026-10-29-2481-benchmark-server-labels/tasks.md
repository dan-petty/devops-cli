# Tasks

## 1. The benchmarks name each server by host and port

- [x] 1.1 Write the failing tests for a dry run, a stub run, a failed run and a server with no origin
  - Verification: `uv run devops ci test tests/test_ai_benchmark.py tests/test_embedding_benchmark.py`
- [x] 1.2 Add `server_label` in `src/devops_cli/ai/benchmark/labels.py`, and use it in both runners and in the setup of the kept run
  - Verification: `uv run devops ci test tests/test_ai_benchmark.py tests/test_embedding_benchmark.py tests/test_embedding_benchmark_failure.py`
- [x] 1.3 Say in the help of `--servers` that a report names a server by `host[:port]`, and regenerate the documents
  - Verification: `uv run devops docs generate --sync-readme`

## 2. A model endpoint is named by its host and port

- [x] 2.1 Write the failing tests that scan the saved report and the kept run for the password
  - Verification: `uv run devops ci test tests/test_ai_benchmark.py tests/test_embedding_benchmark.py`
- [x] 2.2 Add `model_label`, name each model by it in `BenchmarkRunner`, and write it in the setup of the kept run
  - Verification: `uv run devops ci test tests/test_ai_benchmark.py tests/test_embedding_benchmark.py`
- [x] 2.3 Say in the help of `--models` that a report names a model endpoint by `host[:port]`, and regenerate the documents
  - Verification: `uv run devops docs generate --sync-readme`

## 3. Errors name a server by its host and port

- [x] 3.1 Write the failing tests for a refused `--servers` entry, a refused endpoint and a failed run
  - Verification: `uv run devops ci test tests/test_ai_benchmark.py tests/test_embedding_benchmark.py tests/test_rag_embeddings.py`
- [x] 3.2 Build the benchmark errors from `server_label`. Name the engine endpoint without userinfo
  - Verification: `uv run devops ci test tests/test_ai_benchmark.py tests/test_embedding_benchmark.py tests/test_rag_embeddings.py`

## 4. Archive

- [x] 4.1 Archive the change
  - Verification: `uv run devops openspec archive 2481-benchmark-server-labels`

## Workflow follow-up

- Pending a person: if a server URL held `user:password` in `ai.ollama_urls`, `--servers` or a `--models` entry, change that password. Then delete the old files in `<data>/benchmarks` and the kept `ai-benchmark` runs. They hold the URL as it was configured.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
