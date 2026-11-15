# Tasks: #4007

- [x] 1.1 Add the offline test `test_a_write_outside_the_read_only_copy_fails` over the rendered Job.
- [x] 1.2 Add the offline test `test_a_read_of_a_credential_and_of_the_service_account_token_finds_no_file`.
- [x] 1.3 Add the offline test `test_an_outbound_connection_fails` over the committed NetworkPolicy.
- [x] 2.1 Add the live test `test_the_run_job_holds_the_three_controls` with the `k8s` marker.
- [x] 2.2 Declare the `k8s` marker in `pyproject.toml` and deselect it in a default run.
- [x] 3.1 Pass `uv run devops ci --check --only lint,format,typecheck,test-tree`.
