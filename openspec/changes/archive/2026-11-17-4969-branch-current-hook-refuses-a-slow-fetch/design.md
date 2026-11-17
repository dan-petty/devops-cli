# Design

## Decisions

### A fixed 45 second limit

The measured fetch took 15.7 seconds at a load average of 67 and more than 20 seconds at 70. A
fixed 45 second limit is about three times the measured time, keeps no state and is deterministic.
A limit from a measured history needs a state file and a cold-start policy.

### The sum fits the agent shell

The agent shell stops the push at 120 seconds. The other pre-push hooks hold 40 and 30 seconds, so
`120 - (40 + 30) = 50`; 45 seconds leaves 5 seconds of slack. A test sums the limits.

### Status 124 is the timeout

`timeout` exits with status 124 when the command runs out of time. The hook captures the fetch
status before it tests it, prints the 45 second message for 124 and the unavailable-origin message
for another nonzero status.

### No git low-speed limits

`http.lowSpeedLimit` and `http.lowSpeedTime` stop a stalled transfer only. A slow transfer that
still makes progress reaches the wall-clock limit, and the message names that limit.

### Test with a stub git

Pytest reads the hook entry, puts a stub `git` on `PATH` and runs the entry with `sh -c`. The test
is offline, fast and runs in the required `Tests & Coverage` check.

## Rejected alternatives

- **A limit from a measured history:** it needs a state file and a cold-start policy.
- **50 seconds:** the sum equals the 120 second budget instead of staying below it.
- **20 seconds:** this is the current value, and a loaded host exceeds it.
- **Git low-speed limits:** they stop only a stalled transfer, not a slow one.
- **A `devops ci` row:** the rule for rows covers static checks; this test starts a program.
