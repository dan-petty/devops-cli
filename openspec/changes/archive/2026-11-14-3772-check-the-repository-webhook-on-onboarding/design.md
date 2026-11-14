# Design

## Decisions

**The row is read-only.** A webhook carries a secret and is a repository setting, so only a person adds or changes it. The row reports the state and the exact step, and it calls no write.

**The URL is a setting.** The Service's public host differs from cluster to cluster, so `service.webhook_url` names the route and the row compares against it. The default is the example host of the ingress manifest.

**A non-matching hook names the fields.** A person learns whether the URL, the content type, the event set or the active flag is wrong from the row alone. When no hook has the URL, the row names `url` and the other fields that differ from the first hook, which the acceptance scenario expects.

**An unreadable list is not a failure.** The installation token of a stage Job has no administration read, so the row catches the operation error, names the login, prints the step, and leaves the exit code to the other rows, as the App-installation row already does.

**One source holds the events.** The row and the step both read `CONST_ROADMAP_WEBHOOK_EVENTS`, and a test compares the step of `docs/CLUSTER.md` step 8 with the constant.

## Rejected alternatives

- **Create the hook.** A write that carries a secret is a person's action (`AGENTS.md`), and the issue says the row writes nothing.
- **Hard-code the URL.** The host differs from cluster to cluster.
- **Fail the command when the hooks are unreadable.** A person's token may lack administration read while the other rows pass, and a failure would hide the step.
