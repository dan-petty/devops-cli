Harden the following vulnerable Kubernetes Deployment manifest to comply with the Kubernetes Restricted Pod Security Standard (PSS/PSA):

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: payment-api
  namespace: production
spec:
  replicas: 3
  selector:
    matchLabels:
      app: payment-api
  template:
    metadata:
      labels:
        app: payment-api
    spec:
      containers:
      - name: api
        image: payment-api:v1.2.0
        ports:
        - containerPort: 8080
```

Output the complete, production-ready YAML manifest.
