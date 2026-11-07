# Design

## Decisions

- **Remove the dead members from `StepClass` and from the constant, and nothing else.** The default ladder, the validator and the test `tests/config/test_k8s_devops_runtime.py` all read `CONST_ROADMAP_IMPLEMENT_STEP_CLASSES`, so they follow with no edit.
- **Add no shim for a live ConfigMap that names `plan` or `review`.** The project is alpha software and keeps no backward compatibility. The validator refuses the key with its existing message, and a person removes the keys from the live ConfigMap in the same deploy.
- **Test the three places that name the classes: the enum, the constant with the default ladder, and the example ConfigMap.** A class added to one place but not the others then fails a test.

## Rejected alternatives

- **Keep `plan` and `review` for #3049.** #3049 is open and has no code. A setting with no effect misleads a person today, and #3049 adds the class back when it builds the review step.
- **Make the validator ignore `plan` and `review` for one release.** This is a compatibility path. Before `1.0.0` the project removes the old path (AGENTS.md).
