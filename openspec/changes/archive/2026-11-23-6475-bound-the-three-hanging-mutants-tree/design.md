# Design

## Decisions

### 128 MiB size limit for parsed source tree
The tree guard checks the total source file size in `tests/support/trees.py`.
If total bytes exceed 128 MiB, the test raises `pytest.skip` naming the generated tree and size.
Normal source files under `src/` use less than 10 MiB.
The mutants tree exceeds 475 MB.

### 60 second duration bound in service memory test
The memory test round loop measures elapsed time with the monotonic clock.
If elapsed seconds exceed 60, the loop skips naming the generated tree and elapsed time.
The loop stops the worker cleanly before skipping.

### Add bounds constants to `tests/support/waits.py`
`tests/support/waits.py` holds test wait and timeout constants.
Add `PARSED_TREE_BOUND_BYTES` and `ROUND_LOOP_BOUND_SECONDS` there.

## Rejected alternatives

- **`pytest-timeout` plugin**: Fails expired tests and cannot produce the required skip reason.
- **Smaller input sample**: Checks only part of `src/devops_cli` and misses defects in other files.
- **Fewer memory test rounds**: Weakens the heap leak detection between round 10 and round 50.
