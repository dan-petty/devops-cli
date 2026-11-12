# Design

## Decisions

- The floor removes `DEVOPS_CLI_ROADMAP_IMPLEMENT_IN_RUNNER` in `isolate_devops_cli_config`. That fixture runs for each test and already sets `DEVOPS_CLI_CONFIG`, the variable of the config file. A setting variable wins over the config file, so the fixture that gives the test its config also removes the runner variable that would override that config.
- The fixture removes the variable, and does not set it to `false`. The default is false, and a test that needs the in-runner path sets `roadmap.implement.in_runner` in its config. A variable set to `false` would win over that config value.
- The new test runs the floor in pytester, with the variable set in the outer environment before the inner run starts. That is the order of the runner pod: the variable is in the environment before pytest starts. A fixture of the same test cannot set the variable before the autouse floor fixture runs.

## Rejected alternatives

- The removal in the `cluster_jobs` fixture of `tests/support/fakes/cluster_jobs.py`, as the issue proposes. With the variable set, `test_confirm_outside_a_runner_exits_1_and_runs_nothing`, `test_the_job_runs_no_step_unless_it_is_in_a_runner` and `test_a_job_outside_a_runner_does_not_touch_its_process` fail too, and none of them uses `cluster_jobs`. A removal in that fixture leaves these 3 tests failing in the runner pod.
- An autouse fixture in each affected test file. It repeats the setup in 3 files and leaves each new test file exposed. `test_roadmap_implement_records.py` shows this form: it removes the variable in the test itself.
- A removal of every `DEVOPS_CLI_` variable from the environment of the run. The floor sets `DEVOPS_CLI_CONFIG`, `DEVOPS_CLI_DATA_DIR`, `DEVOPS_CLI_USER_DATA_ROOT` and other variables itself, and a run can pass a variable on purpose. The runner manifest sets only one variable that the floor does not set.
