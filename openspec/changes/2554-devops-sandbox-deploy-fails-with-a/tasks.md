# Tasks

## 1. Add pull_image to DockerEngineService

Reads: none. Changes: `src/devops_cli/docker/engine.py`, `src/devops_cli/docker/sdk.py`.

- [ ] 1.1 Write a test that calls pull_image with an image not in the fake. Assert images.get was called first, then images.pull was called with the image reference. Write a test that calls pull_image with an image present in the fake. Assert images.pull was not called. Write a test that calls pull_image when the pull fails. Assert the raised DockerEngineError message contains the image reference and the failure reason, and verify that `uv run devops ci test tests/docker/test_engine_pull_image.py` fails on the base
- [ ] 1.2 Add a pull_image method to DockerEngineService. It calls self.client().images.get(image) in a try block. If the image is found, return. If ImageNotFound is raised, call self.client().images.pull(image). If the pull raises, raise DockerEngineError with the image reference and the failure reason in the message. Add get and pull to the EngineImage protocol in sdk.py if they are not already declared, and verify that `uv run devops ci test tests/docker/test_engine_pull_image.py` passes
- [ ] 1.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 2. Add image pull support to DockerEngineFake

Reads: none. Changes: `tests/support/fakes/docker_engine.py`.

- [ ] 2.1 Write a contract test case that scripts an image pull on the fake. Assert the call is recorded in calls. Write a case that makes the pull fail. Assert the error propagates with the image reference in the message, and verify that `uv run devops ci test tests/docker/test_engine_contract.py` fails on the base
- [ ] 2.2 Add images.get and images.pull methods to the fake image collection. images.get raises ImageNotFound when the image is absent from the local set. images.pull records the call and adds the image to the local set. A fail method makes the pull raise a DockerException with a given message, and verify that `uv run devops ci test tests/docker/test_engine_contract.py` passes
- [ ] 2.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 3. Pull image in sandbox deploy before create

Reads: none. Changes: `src/devops_cli/docker/sandbox.py`.

- [ ] 3.1 Write a test that runs WorkloadSandboxRunner.run with an image not in the fake. Assert pull_image was called before create_container. Write a test with the image present in the fake. Assert no pull call was made. Write a test where pull fails. Assert the error message names the image reference, and verify that `uv run devops ci test tests/docker/test_sandbox_deploy_pull.py` fails on the base
- [ ] 3.2 In WorkloadSandboxRunner.run, call engine.pull_image(self.config.image) before engine.create_container. The call sits inside the trace_span block, immediately before the create_container line. No other change to the run method, and verify that `uv run devops ci test tests/docker/test_sandbox_deploy_pull.py` passes
- [ ] 3.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
