# Tasks

## 1. Qdrant retry uses tenacity sleep parameter

Reads: `src/devops_cli/ai/rag/qdrant.py`, `tests/test_rag_multi_project_indexer.py`, `tests/support/fakes/clock.py`. Changes: `src/devops_cli/ai/rag/qdrant.py`, `tests/test_rag_multi_project_indexer.py`.

- [x] 1.1 Write a test in tests/test_rag_multi_project_indexer.py that runs the retry on the clock fixture and asserts the recorded waits match the expected backoff sequence of 0.5, 1.0, 1.5 seconds for three attempts., and verify that `uv run devops ci test tests/test_rag_multi_project_indexer.py` fails on the base
- [x] 1.2 Replace the time.sleep(0.5 * attempt) in _record_retry with tenacity's sleep parameter. The retry loop passes a sleep function that calls the clock seam's sleep. Remove the time import if no longer needed in the module., and verify that `uv run devops ci test tests/test_rag_multi_project_indexer.py` passes
- [x] 1.3 None., run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 2. Process fake delay advances clock

Reads: `tests/support/fakes/process.py`, `tests/support/fakes/clock.py`. Changes: `tests/support/fakes/process.py`.

- [x] 2.1 Write a test that scripts a ProcessAnswer with a delay of 2.0 and a timeout of 5.0, runs it through ProcessFake.run, and asserts the clock advanced by 2.0 and no real time was spent. Write a second test where the delay is 10.0 and the timeout is 5.0, and asserts the timeout error is raised at once with no sleep., and verify that `uv run devops ci test tests/test_ai_review_pool.py tests/test_memory_profiler.py tests/test_server_service.py` fails on the base
- [x] 2.2 In ProcessFake.run and run_async, replace the time.sleep and asyncio.sleep calls for the delay with a call to the clock fixture's advance method. When the delay exceeds the timeout, raise the timeout error immediately without any sleep., and verify that `uv run devops ci test tests/test_ai_review_pool.py tests/test_memory_profiler.py tests/test_server_service.py` passes
- [x] 2.3 None., run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 3. Test bodies batch 1: ai client and argo

Reads: `tests/test_ai_client_network.py`, `tests/test_ai_client_security.py`, `tests/test_ai_review_pool.py`, `tests/test_argo_gitops.py`, `tests/support/waits.py`, `tests/support/fakes/clock.py`. Changes: `tests/test_ai_client_network.py`, `tests/test_ai_client_security.py`, `tests/test_ai_review_pool.py`, `tests/test_argo_gitops.py`.

- [x] 3.1 For each of the four files, write or update the test to wait for the event that the code under test signals, or to run on the clock fixture and assert the recorded waits. Remove the time.sleep and asyncio.sleep calls., and verify that `uv run devops ci test tests/test_ai_client_network.py tests/test_ai_client_security.py tests/test_ai_review_pool.py tests/test_argo_gitops.py` fails on the base
- [x] 3.2 In tests/test_ai_client_network.py:251, replace time.sleep with a wait on the event the code signals. In tests/test_ai_client_security.py:296, replace time.sleep with the clock fixture. In tests/test_ai_review_pool.py:52,106,119, replace asyncio.sleep and time.sleep with the clock fixture or an event wait. In tests/test_argo_gitops.py:87,223, replace time.sleep with an event wait via tests/support/waits.py., and verify that `uv run devops ci test tests/test_ai_client_network.py tests/test_ai_client_security.py tests/test_ai_review_pool.py tests/test_argo_gitops.py` passes
- [x] 3.3 None., run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 4. Test bodies batch 2: devcontainer, github, http, k8s

Reads: `tests/test_devcontainer.py`, `tests/test_github_session.py`, `tests/test_http_egress.py`, `tests/test_k8s_service.py`, `tests/support/waits.py`, `tests/support/fakes/clock.py`. Changes: `tests/test_devcontainer.py`, `tests/test_github_session.py`, `tests/test_http_egress.py`, `tests/test_k8s_service.py`.

- [x] 4.1 For each of the four files, write or update the test to wait for the event that the code under test signals, or to run on the clock fixture and assert the recorded waits. Remove the time.sleep and asyncio.sleep calls., and verify that `uv run devops ci test tests/test_devcontainer.py tests/test_github_session.py tests/test_http_egress.py tests/test_k8s_service.py` fails on the base
- [x] 4.2 In tests/test_devcontainer.py:1978, replace time.sleep with an event wait. In tests/test_github_session.py:443, replace time.sleep with the clock fixture. In tests/test_http_egress.py:435,460, replace time.sleep and asyncio.sleep with the clock fixture. In tests/test_k8s_service.py:516, replace time.sleep with an event wait via tests/support/waits.py., and verify that `uv run devops ci test tests/test_devcontainer.py tests/test_github_session.py tests/test_http_egress.py tests/test_k8s_service.py` passes
- [x] 4.3 None., run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 5. Test bodies batch 3: ollama, pydantic, rag, response

Reads: `tests/test_ollama_dynamic_leasing.py`, `tests/test_pydantic_agent.py`, `tests/test_rag_investigator.py`, `tests/test_rag_query_telemetry.py`, `tests/support/waits.py`, `tests/support/fakes/clock.py`. Changes: `tests/test_ollama_dynamic_leasing.py`, `tests/test_pydantic_agent.py`, `tests/test_rag_investigator.py`, `tests/test_rag_query_telemetry.py`.

- [x] 5.1 For each of the four files, write or update the test to wait for the event that the code under test signals, or to run on the clock fixture and assert the recorded waits. Remove the time.sleep calls., and verify that `uv run devops ci test tests/test_ollama_dynamic_leasing.py tests/test_pydantic_agent.py tests/test_rag_investigator.py tests/test_rag_query_telemetry.py` fails on the base
- [x] 5.2 In tests/test_ollama_dynamic_leasing.py:61, replace time.sleep with the clock fixture. In tests/test_pydantic_agent.py:497, replace time.sleep with an event wait. In tests/test_rag_investigator.py:177, replace time.sleep with the clock fixture. In tests/test_rag_query_telemetry.py:279, replace time.sleep with an event wait via tests/support/waits.py., and verify that `uv run devops ci test tests/test_ollama_dynamic_leasing.py tests/test_pydantic_agent.py tests/test_rag_investigator.py tests/test_rag_query_telemetry.py` passes
- [x] 5.3 None., run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 6. Test bodies batch 4: cache, review, telemetry, watchers

Reads: `tests/test_response_cache.py`, `tests/test_review_adjudication.py`, `tests/test_telemetry.py`, `tests/test_telemetry_collector_export.py`, `tests/test_watchers.py`, `tests/test_memory_profiler.py`, `tests/test_server_service.py`, `tests/support/waits.py`, `tests/support/fakes/clock.py`. Changes: `tests/test_response_cache.py`, `tests/test_review_adjudication.py`, `tests/test_telemetry.py`, `tests/test_telemetry_collector_export.py`, `tests/test_watchers.py`, `tests/test_memory_profiler.py`, `tests/test_server_service.py`.

- [x] 6.1 For each of the seven files, write or update the test to wait for the event that the code under test signals, or to run on the clock fixture and assert the recorded waits. Remove the time.sleep and asyncio.sleep calls., and verify that `uv run devops ci test tests/test_response_cache.py tests/test_review_adjudication.py tests/test_telemetry.py tests/test_telemetry_collector_export.py tests/test_watchers.py tests/test_memory_profiler.py tests/test_server_service.py` fails on the base
- [x] 6.2 In tests/test_response_cache.py:147, replace time.sleep with the clock fixture. In tests/test_review_adjudication.py:301, replace time.sleep with an event wait. In tests/test_telemetry.py:678, replace time.sleep with the clock fixture. In tests/test_telemetry_collector_export.py:172, replace time.sleep with an event wait via tests/support/waits.py. In tests/test_watchers.py:68, replace time.sleep with the clock fixture. In tests/test_memory_profiler.py:182, replace asyncio.sleep with the clock fixture. In tests/test_server_service.py:500, replace asyncio.sleep with an event wait., and verify that `uv run devops ci test tests/test_response_cache.py tests/test_review_adjudication.py tests/test_telemetry.py tests/test_telemetry_collector_export.py tests/test_watchers.py tests/test_memory_profiler.py tests/test_server_service.py` passes
- [x] 6.3 None., run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
