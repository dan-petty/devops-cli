Analyze the following GitHub Actions workflow snippet that exhibits intermittent deployment race conditions and duplicate concurrent deployments to staging:

```yaml
name: Deploy Staging
on:
  push:
    branches: [ 'feat/*', 'release/*' ]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - run: ./deploy.sh staging
```

Identify the concurrency issues and provide a corrected, robust workflow with proper concurrency groups, cancel-in-progress semantics, and minimum permission principles (least privilege).
