## REMOVED Requirements

### Requirement: Secret reference guard yields mounted Secret names
**Reason**: The guard was a helper of the test that compared the manifests with the cluster Secret table, and #6119 deletes that test (#6060).
**Migration**: A pod that references a Secret with no row does not start: `kubectl get pods` shows `CreateContainerConfigError`, and Argo CD shows the Application as degraded.
