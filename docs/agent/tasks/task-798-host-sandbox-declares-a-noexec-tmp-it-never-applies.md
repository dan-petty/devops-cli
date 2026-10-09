# Task: The Host Sandbox Declares a Noexec /tmp It Never Applies (#798)

**Issue**: [#798](https://github.com/dan-petty/devops-cli/issues/798)
**Status**: Done
**Milestone**: v0.2.32
**Priority**: priority/p3-low
**Scope**: type/security, scope/security

## Description

The host sandbox (`src/devops_cli/sandbox/host.py`) read the same `SandboxPolicy` as the container
runners, whose `/tmp` is `size=64m,noexec`. Only the size reached bubblewrap. The `noexec` flag was
dropped without a word. With bubblewrap 0.13.0, `bwrap --help` lists only `--size` (and `--perms`)
as modifiers for `--tmpfs`, with no noexec option. Inside the sandbox, `/proc/self/mounts` showed
`/tmp` as `rw,nosuid,nodev,size=65536k`, and a script written to `/tmp` ran.

The host sandbox cannot enforce noexec. The confined child has no capabilities to remount `/tmp`.
Landlock would need a dependency outside the standard library. And noexec would not stop
`sh /tmp/x` anyway. So the host policy now declares only what bubblewrap applies, and
SECURITY.md says that the host sandbox's `/tmp` allows execution. The container policy
(`DEFAULT_SANDBOX_POLICY`) keeps `size=64m,noexec`. Whether the container engines enforce it is a
question for the audit in #698.

The output-cap test used a writer that exited by itself after 50 KB, so it never showed that the
sandbox kills a process at the cap. An endless writer such as `yes` is not enough either: it dies
of SIGPIPE once the sandbox closes its pipes. The test now runs a shell loop that ignores SIGPIPE,
so only the kill at the cap ends it within the reap's 1 s grace.

The host policy still declares a `pids_limit` that the host sandbox ignores, as
`_run_sandbox_process` documents: bubblewrap has no process limit, and RLIMIT_NPROC is per user,
not per process tree. `SandboxPolicy.pids_limit` is an `int` with no "no limit" value, and the
container runners apply it, so dropping it from the host policy changes the shared model and is
outside this item. No issue tracks it: #698 audits the container runners only, and #772, which
adds the host sandbox's resource limits, sets no process-count limit but does not cover the
declared value.

## Key Changes

- `src/devops_cli/sandbox/host.py`:
  - `DEFAULT_HOST_SANDBOX_POLICY` declares `/tmp` as `size=64m`, and `HostSandbox` defaults to it.
  - `_tmpfs_mount_args(path, options)` replaces the regex in `_parse_tmpfs_size_bytes`. It turns a
    `size` option into `--size <bytes>` with `docker.utils.parse_bytes` (the existing `docker`
    dependency) and raises `SandboxValidationError` naming any other option, or a size that
    `parse_bytes` refuses (such as `size=50%`), instead of dropping it.
  - `HostSandbox.__init__` builds the tmpfs arguments once, so a policy that bubblewrap cannot
    apply fails when the sandbox is constructed, not when it runs a command.
- `SECURITY.md`, item 6 ("Host Sandbox Confinement"): the host sandbox's `/tmp` is a private
  64 MiB tmpfs mounted nosuid and nodev, which the confined command can write to and execute from.
- `tests/test_host_sandbox.py`:
  - `test_host_sandbox_default_policy_mounts_tmp_as_declared` and
    `test_host_sandbox_refuses_a_tmpfs_option_bubblewrap_cannot_apply` are new.
  - `test_host_sandbox_kills_an_endless_writer_at_the_output_cap` replaces
    `test_host_sandbox_kills_process_exceeding_output_cap`.
  - `test_sandbox_binds_the_virtualenv_interpreter_installation_read_only` builds its writable
    policy from `DEFAULT_HOST_SANDBOX_POLICY`.

## Acceptance Criteria

- [x] **The host stops declaring noexec.** `test_host_sandbox_default_policy_mounts_tmp_as_declared` shows that the default host policy declares `/tmp` as `size=64m` and that the arguments mount it with `--size 67108864 --tmpfs /tmp`.
- [x] **An option bubblewrap cannot apply is refused.** `test_host_sandbox_refuses_a_tmpfs_option_bubblewrap_cannot_apply` constructs host sandboxes whose policies declare `size=64m,noexec` and `size=50%`, and expects a `SandboxValidationError` naming `noexec` and `size=50%`.
- [x] **Containers keep noexec.** `DEFAULT_SANDBOX_POLICY` in `src/devops_cli/sandbox/models.py` is unchanged, and `tests/test_sandbox_lifecycle.py` still pins its `size=64m,noexec` tmpfs.
- [x] **The docs say which.** SECURITY.md item 6 says that the host sandbox's `/tmp` allows execution, and why.
- [x] **The cap kills an endless writer.** `test_host_sandbox_kills_an_endless_writer_at_the_output_cap` (bubblewrap-marked) runs a shell loop that ignores SIGPIPE, with a 30 s timeout and a 1024-byte cap. It asserts that the run fails without timing out, keeps at most 1024 bytes, reports the cap, and ends within 1 s. That is under the reap's 1 s grace, so the test fails if the kill at the cap is removed (the run then takes about 1.06 s, or about 2.09 s with no kill at all).
- [x] **No RLIMIT_NPROC and no fork bombs.** No test sets a process limit or spawns processes without bound.
- [x] **Release.** `changelog.d/798.md` records the change under `### Security`.
