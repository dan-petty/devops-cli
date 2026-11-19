# Tasks

## 1. The contract suite

Kind: test-only edit. Changes: `tests/support/valkey_scenarios.py`, `tests/valkey/test_valkey_contract.py`.

- [x] 1.1 Write the scenarios (`SET NX EX`, `SET EXAT`, `HINCRBY`, `ZADD` with a trim, valkey-py `Lock` acquire, extend, `owned()` and release, Lua through `register_script`, and `EVAL`) and the suite that runs each scenario over the fake. Before the `lua` extra, the fake side fails on the Lua and `Lock` cases.
  - Verification: `$ uv run devops ci test tests/valkey/test_valkey_contract.py`

## 2. The dependency

Kind: data. Changes: `pyproject.toml`, `uv.lock`.

- [x] 2.1 Pin `fakeredis[lua,valkey]==2.40.0` in the `dev` group and run `uv lock`, so `lupa` installs and the fake side of the suite passes.
  - Verification: `$ uv lock --check`

## 3. The record and replay support

Kind: test-only edit. Changes: `tests/support/valkey_replay.py`, `tests/support/valkey_recording.py`, `tests/fixtures/valkey/recorded_exchanges.json`, `tests/valkey/test_valkey_contract.py`.

- [x] 3.1 Write `RecordedValkey`: it serves the recorded replies of one scenario in order on a socket that the test binds, answers a request that is not the next recorded one with an error reply, and keeps it in `unexpected`. `remaining` counts the replies that no request took.
  - Verification: `$ uv run devops ci test tests/valkey/test_valkey_contract.py`
- [x] 3.2 Write the recorder, and record each scenario against a new, empty `valkey-server` on a loopback port with no persistence: the unpacked Debian package on a workstation, or a temporary Pod of the official image `valkey/valkey` with a port-forward. The record keeps the server version and the valkey-py version.
  - Verification: `$ uv run devops ci test tests/valkey/test_valkey_contract.py`
- [x] 3.3 Run each scenario over a real valkey-py client on `RecordedValkey`. Assert that both sides give the same result, that `unexpected` is empty and `remaining` is 0, and that the suite fails when the record is not of the locked valkey-py version.
  - Verification: `$ uv run devops ci test tests/valkey/test_valkey_contract.py`
- [x] 3.4 Confirm that the record holds no host path, hostname or private address.
  - Verification: `$ ! git grep -n -F -e /home/ -e /workspaces/ -e /tmp/ -e .lan -e 192.168. -e 172.16. -- tests/fixtures/valkey/recorded_exchanges.json`

## 4. Documents

Kind: documents. Changes: `docs/TESTING.md`, `tests/support/fakes/valkey.py`.

- [x] 4.1 Name the suite in the Valkey paragraph and in the list of fakes of `docs/TESTING.md`, and in the docstring of `tests/support/fakes/valkey.py`, in place of each statement that the fake has no contract suite.
  - Verification: `$ ! git grep -n -e "has no contract suite yet, since no recorded exchange" -e "The fake has no contract suite" -- docs tests src`
- [x] 4.2 Run the documentation check.
  - Verification: `$ uv run devops ci --check --only docs`

## Workflow follow-up

- The `limits` moving-window `hit` case: #4563 adds `limits` and adds the case to this suite.
