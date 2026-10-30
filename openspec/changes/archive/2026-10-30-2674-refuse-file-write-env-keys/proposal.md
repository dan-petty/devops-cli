# Proposal

## Why

Issue #2674: the subprocess environment guard accepts the keys that make a child write TLS secrets, a log or a profile to a file that the caller names.

- `build_subprocess_env` in `src/devops_cli/core/process.py` refuses a caller override that `CONST_CODE_LOADING_ENV_PATTERNS` matches. #2483 refuses `GIT_TRACE`, `GIT_TRACE2` and `GIT_TRACE_CURL`, because git appends to a file that the caller names. The patterns hold no key of the same kind for curl, Node.js or the glibc loader.
- `SSLKEYLOGFILE` makes `curl`, `git` over HTTPS and the `ssl` module of Python write the TLS secrets of each connection to the file that the key names. A person who reads the file can decrypt the recorded traffic of the child.
- `QLOGDIR` makes `curl` write a QUIC log to a directory. `NODE_V8_COVERAGE` makes Node.js write coverage data to a directory, and `NODE_REDIRECT_WARNINGS` makes it write its warnings to a file.
- `LD_DEBUG_OUTPUT` and `LD_PROFILE_OUTPUT` make the glibc loader write its debug text and its profile data to a file or a directory. They act with `LD_DEBUG` and `LD_PROFILE`.

## What Changes

- The guard refuses `SSLKEYLOGFILE`, `QLOGDIR`, `NODE_V8_COVERAGE` and `NODE_REDIRECT_WARNINGS` as a caller override. Each raises the same `SecurityError` as the other refused keys, with isolation on and off.
- The guard refuses each `LD_` key of the glibc loader, as it refuses each `GIT_` and `SSH_` key. The four `LD_` names of the constant become the one pattern `LD_*`.
- The guard keeps accepting `PYTHONDUMPREFSFILE` and `GPGRT_TRACE_FILE`. No probe made a child write a file with them (Feasibility). The design gives the reason.
- `ARCHITECTURE.md` names the new refused keys. The refusal is what a consumer sees, so the change adds requirements to the `subprocess-environment` spec.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `subprocess-environment`: the guard refuses the keys that make a child write a file that the caller names. The change adds requirements and rewrites no existing requirement.

## Impact

- Code: `src/devops_cli/config/constants.py` (one new block of `CONST_CODE_LOADING_ENV_PATTERNS`, and the `LD_*` pattern in place of four names).
- Tests: `tests/test_subprocess_env_file_write.py`.
- Documents: `ARCHITECTURE.md`.

## Feasibility

The guard accepts the keys today. On `origin/main` at `ad0bdf1f`, `build_subprocess_env(env={"SSLKEYLOGFILE": "x"})` returns the key with no `SecurityError`, for each key of the list above.

Each probe ran on Linux with `env -i`, a temporary `HOME`, `PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring`, a fake value and a scratch directory that the probe could write. Only loopback addresses were used. The HTTPS server was a throwaway Python server on `127.0.0.1` with a certificate that `openssl` made for the probe. The server stopped after the probe. A control run of curl with no key made no file. The tools: curl 8.23.0 (OpenSSL 3.6.5, ngtcp2 1.24.0), git 2.55.0, Python 3.14.10, Node.js v24.22.2, glibc 2.43, gpg 2.4.9.

- `SSLKEYLOGFILE` made `curl -s https://127.0.0.1:<port>/` write `keys.log`. It holds the lines `CLIENT_HANDSHAKE_TRAFFIC_SECRET`, `CLIENT_TRAFFIC_SECRET_0`, `EXPORTER_SECRET`, `SERVER_HANDSHAKE_TRAFFIC_SECRET` and `SERVER_TRAFFIC_SECRET_0`. `git ls-remote https://127.0.0.1:<port>/x.git` wrote the same lines to `keys.log` (git exited with 128, because the server does not speak the git protocol, but the handshake had finished). `urllib.request.urlopen` with `ssl.create_default_context()` wrote the same lines to `keys.log`.
- `QLOGDIR` made `curl --http3-only` to a closed loopback port write a file `<hash>.sqlog` with a QUIC log in the `qlog` JSON-SEQ format. curl exited with 7, and the file stayed.
- `NODE_V8_COVERAGE` made `node -e 1+1` write `coverage-<pid>-<time>-0.json` in the directory of the key.
- `NODE_REDIRECT_WARNINGS` made `node -e "process.emitWarning('probe-warning')"` write the warning text to the file of the key.
- `LD_DEBUG=files` with `LD_DEBUG_OUTPUT=<dir>/dbg` made `/bin/true` write `<dir>/dbg.<pid>` with loader debug text. `LD_DEBUG=files` alone wrote nothing to a file. `LD_PROFILE=libc.so.6` with `LD_PROFILE_OUTPUT=<dir>` made `ssh -V` write `<dir>/libc.so.6.profile`, a `gmon` profile file. The comment on the issue reports the same two probes with OpenSSH 10.6p1.
- Keys that no probe confirmed: `PYTHONDUMPREFSFILE` made `python -c pass` write no file. The `python(1)` page ties it to a build with `Py_TRACE_REFS`, and the interpreters here have `Py_TRACE_REFS` off. `GPGRT_TRACE_FILE` is a string of `libgpg-error.so.0`, but `gpg --version`, `gpg --list-keys`, `gpg --gen-random`, `gpgconf --list-options`, `gpg --version --debug-all` and `gpg-connect-agent --no-autostart /bye` wrote no file with it.
- The callers: no file of `src/` or `tests/` gives one of the refused keys as a caller override. The only match for an `LD_` name outside the constant is the boundary test of the four loader keys.

## Existing Tool Considered

The default `env_delete` table of sudo is the maintained, open list of environment keys that change the code that a program runs. It lists `LD_*`, and it lists none of the other four keys. No library publishes a list for import, so the constant names the source of each key, as #2205, #2429, #2483, #2633 and #2672 decided. The match keeps `fnmatch.fnmatchcase` of the standard library. The change builds no new code path: it adds four names and one pattern to the existing tuple. Written cost: about 1500 tokens to build, keep and fix it, and under one hour elapsed.
