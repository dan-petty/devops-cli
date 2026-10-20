# Task: The Dashboard's Reactive Tests Run in Half Today's Time and Still Check Every Behaviour (#1339)

**Issue**: [#1339](https://github.com/dan-petty/devops-cli/issues/1339)
**Scope**: scope/cli
**Feasibility**: In Textual 8.2.8, `pilot.press` waits twice per key, and `pilot.pause()` once, for the process to go idle (under 1 ms of CPU in a 20 ms window), each time for up to one second. Profiling the tests at the base showed three things kept the process busy:
- each tab switch's 0.3s underline animation;
- the endless log source in the stream tests, writing a line every 2 ms, which held every key at the one-second cap;
- six tests in `tests/test_ui_dashboard.py` listing the workstation's real Docker engine, at 2-10s per test.

## Description

- [x] `tests/conftest.py` sets Textual's own `TEXTUAL_ANIMATIONS=none` before Textual is imported. Animator waits went from 1.5-3.7s to 0.01s.
- [x] The lifecycle, refresh-before-mount and four `--summary` dashboard tests use an `empty_docker_engine` fixture built on the shared `docker_engine` double. Docker calls went from 2.2-9.6s to 0.02s per test. No devops-cli name is patched.
- [x] Fixed pauses became waits on conditions:
  - `_settle` polls its condition every `POLL_INTERVAL_SECONDS` under `THREAD_HANDOFF_BOUND_SECONDS`, pumping the UI between reads.
  - The switch and stop tests wait, through `_stream_ended`, for the old stream's reader thread and consumer worker to end.
  - The quit test waits for `q` to stop the app, and asserts it.
  - The daemon-reader test waits for the reader to enter its read.
  - The endless log source writes a line every 10 ms.
- [x] Every assertion is kept, and the quit and stop tests now also check that the app stopped and the stream ended.
  - With the stop flag removed from `start_stream` and `stop_stream`, the stop test and both switch tests fail.
  - Product code is unchanged, and the files are neither moved nor split.
- [x] Measured with base and change side by side at load 32-42 (`-n 0`, summed): 224.1s to 140.9s in total; `tests/test_ui_dashboard.py` 50.0s to 8.1s; `tests/test_ui_reactive.py` 174.1s to 132.8s. Per test, the lifecycle test went from 18.0s to 6.3s (about 2s at load 9-17), and the second-pod switch from 10.4s to 2.9s. The reactive gain shrinks under higher load, where a starved process stretches the real work.
- Pending a person: the baseline median of three single-process runs of `tests/test_ui_reactive.py` on an otherwise idle devcontainer, as the issue states (79-90s on 2026-10-07). The host never went idle during this work.
- Pending a person: after the change, that median is at most half its baseline, and no test's call phase takes more than 2s.
