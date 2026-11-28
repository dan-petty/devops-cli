## ADDED Requirements

### Requirement: A volume move refuses an Application that an ApplicationSet restores
For each Argo CD Application that the move would pause, the plan SHALL check `metadata.ownerReferences` for an `argoproj.io/v1alpha1` `ApplicationSet`. When one owns the Application and its `spec.ignoreApplicationDifferences` does not cover `/spec/syncPolicy/automated/enabled` for that Application, the plan SHALL raise `VolumeMoveRefusedError` naming the ApplicationSet and `/spec/syncPolicy`, and SHALL change nothing.

#### Scenario: Owned Application without a pause ignore
- **WHEN** `plan_volume_move` reads an Application that it would pause, owned by an `ApplicationSet` whose `spec.ignoreApplicationDifferences` holds only `/spec/source/kustomize/images`
- **THEN** the plan raises `VolumeMoveRefusedError` naming the ApplicationSet and `/spec/syncPolicy`
- **AND** the cluster gets no request that changes it

#### Scenario: ApplicationSet ignores the pause field
- **WHEN** `plan_volume_move` reads an Application that it would pause, owned by an `ApplicationSet` whose `spec.ignoreApplicationDifferences` covers `/spec/syncPolicy` or `/spec/syncPolicy/automated/enabled` for that Application
- **THEN** the plan includes the Application in `paused` and returns the move plan without refusal

#### Scenario: Application without an ApplicationSet owner
- **WHEN** `plan_volume_move` reads an Application whose `metadata.ownerReferences` holds no `ApplicationSet`
- **THEN** the plan pauses and moves the Application without reading any `ApplicationSet`
