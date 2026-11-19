# Proposal: #4557

## Why

The Valkey fake, fakeredis's in-memory server behind `tests/support/fakes/valkey.py`, answers `unknown command 'eval'` and `unknown command 'evalsha'`, because `lupa` is not installed. Each valkey-py `Lock` and each Lua script uses these commands, and the move of Service state into Valkey uses both (ADR 0021). Also the fake has no contract suite, and `docs/TESTING.md` says: "A fake without a contract suite does not merge". Closes #4557.

## What Changes

- The `dev` dependency group pins `fakeredis[lua,valkey]==2.40.0`, so `lupa` installs and the fake answers `EVAL`, `EVALSHA` and `SCRIPT`.
- `tests/support/valkey_scenarios.py` holds the shared scenarios: `SET NX EX`, `SET EXAT`, `HINCRBY`, `ZADD` with a trim, valkey-py `Lock` acquire, extend, `owned()` and release, and Lua through `register_script` and `EVAL`.
- `tests/support/valkey_recording.py` records the request and reply of each scenario through a proxy in front of a real `valkey-server` on loopback. A person runs it outside pytest. The record is `tests/fixtures/valkey/recorded_exchanges.json`, with the server version and the valkey-py version.
- `tests/support/valkey_replay.py` holds `RecordedValkey`, which replays the record on a socket that the test binds.
- `tests/valkey/test_valkey_contract.py` runs each scenario over the fake and over a real valkey-py client on `RecordedValkey`. Both sides must give the same result.
- `docs/TESTING.md` and the docstring of `tests/support/fakes/valkey.py` name the suite in place of the statements that the fake has no contract suite.
- The change alters only tests, a test dependency and documents. No command, option, message, manifest or Service behavior changes, so a consumer sees no change. The change has no spec delta and sets `skip_specs: true`.

### Design correction

The issue body tells pytest to start a real `valkey-server` from `PATH` and to skip the real cases when the binary is missing. That design breaks four rules of `docs/TESTING.md` at `origin/main` 0d90de50b:

- Line 75: a test of `src/` starts no system program.
- Line 76: every other real tool goes to a contract suite that replays recorded transcripts, or to a row of `devops ci`.
- Line 78: a test must not skip based on host state.
- Line 87: every fake has a contract suite, run against the fake and against the real implementation over recorded responses or a real local tool, never a live service.

Also, the hermetic floor (lines 264 and 278) fails a connect to a loopback port that the test process did not bind. This change follows the record-and-replay design of the Docker engine contract suite (line 284) instead. The issue comment of 2026-11-19 gives the correction.

### The `limits` case

`limits` is not a dependency of this repository: `uv.lock` has no entry for it. This change does not add it. #4563 adds `limits`, and it adds the moving-window `hit` case to this suite.

## Capabilities

None. The change is test-only and has no spec delta.

## Impact

- `lupa` 2.8 installs in the `dev` group only. The runtime dependencies do not change.
- The local test row gets one more suite. The pull request gives the measured seconds and the command that measured them. The target is well under 5 s.
- No workflow, manifest or image changes. No host gets a new package.
- The change fits one pull request.

## Feasibility

- At `origin/main` 0d90de50b, `uv.lock` pins `fakeredis` 2.40.0 and `valkey` (valkey-py) 6.2.0, and `pyproject.toml:128` pins `fakeredis[valkey]==2.40.0`.
- `importlib.util.find_spec("lupa")` gives `None`. On a `FakeValkey` over a `FakeServer`, `EVAL 'return 1' 0` gives `ResponseError unknown command 'eval', with args beginning with:`, and `EVALSHA` gives `ResponseError unknown command 'evalsha', with args beginning with:`.
- The fakeredis 2.40.0 metadata declares `lupa>=2.1; extra == 'lua'`.
- `lupa` 2.8 (PyPI, released 2026-04-15) has the MIT license and the classifier `Development Status :: 5 - Production/Stable`. Stefan Behnel, a core developer of Cython, maintains it, with five releases from 2025-01 to 2026-04. It ships a `cp314` manylinux x86_64 wheel. It meets the project rule for a reputable, maintained, permissive dependency.
- valkey-py 6.2.0 `Script.__call__` answers `NOSCRIPT` with `SCRIPT LOAD` and a second `EVALSHA` (`valkey/commands/core.py`), not with `EVAL`. The scenarios record this real fallback, and a separate scenario sends `EVAL`.
- valkey-py 6.2.0 sends `CLIENT SETINFO LIB-NAME` and `CLIENT SETINFO LIB-VER` on each new connection (`valkey/connection.py:436`). The request bytes therefore depend on the valkey-py version, and the record keeps that version.
- `command -v valkey-server` finds nothing in the devcontainer (Debian forky/sid). `apt-cache policy valkey-server` gives the candidate 9.1.4-1. The recorder needs no host install: it records from that binary in a downloaded package, or from a temporary Pod of the official image `valkey/valkey`. The record at hand came from a new, empty Pod of `valkey/valkey:9.1.4-alpine` through a port-forward.
- `git grep -n "no contract suite" -- docs tests src` finds the Valkey statements at `docs/TESTING.md:278` and `tests/support/fakes/valkey.py:8`. ADR 0021 (line 284) plans this suite before the first step that uses a lock. That record is accepted, so its body does not change (`docs/adr/README.md`), and this change fulfills the plan without a `Status History` line.

## Existing Tool Considered

- **fakeredis with `lupa`** covers Lua in the fake. The `lua` extra is the documented way to get `EVAL` and `EVALSHA`. The change adds no Lua shim of its own.
- **The Valkey release binary**, from the Debian package `valkey-server` or the official image `valkey/valkey`, gives the real answers for the record. It runs only when a person records again, outside pytest, on a loopback port with no persistence.
- **The record-and-replay pattern of the Docker engine suite** (`tests/support/docker_engine_recording.py`, `tests/support/docker_engine_replay.py`) gives the form of the recorder, the replay and the version check.
- `pytest-redis` and `testcontainers` start a real server or a container from pytest. Rules 75 and 87 of `docs/TESTING.md` refuse both. This plan found no maintained Python package that records and replays RESP exchanges. The recorder and the replay are new test code, about 400 lines. Cost: about 80,000 tokens and 4 hours to build, about 5,000 tokens a month to keep, and about 10,000 tokens to fix.
- The change deletes no internal code.
