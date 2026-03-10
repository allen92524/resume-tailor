# ArgoCD GitOps Deployment

This directory contains the ArgoCD Application manifest for automated GitOps deployment of Resume Tailor.

## Prerequisites

- A Kubernetes cluster with [ArgoCD](https://argo-cd.readthedocs.io/en/stable/getting_started/) installed
- `kubectl` configured to access your cluster
- Your `ANTHROPIC_API_KEY` ready

## Setup

### 1. Create the API key secret

```bash
kubectl create secret generic resume-tailor-api-key \
  --from-literal=api-key=$ANTHROPIC_API_KEY
```

### 2. Apply the ArgoCD application

```bash
kubectl apply -f argocd/application.yaml
```

### 3. Done

After this, any push to `main` that changes files under `helm/resume-tailor/` will automatically trigger a sync and redeploy the application.

## Quick setup (via Make)

```bash
make argocd-setup    # Creates the secret and applies the ArgoCD application
make argocd-status   # Shows the current sync status
```

## How it works

- ArgoCD watches the `helm/resume-tailor` path in the GitHub repo
- When changes are detected on `main`, ArgoCD automatically syncs the Helm chart to the cluster
- **Self-heal** is enabled: manual changes to the cluster are reverted to match Git
- **Prune** is enabled: resources removed from the chart are deleted from the cluster

## Passing the API key

The Helm chart creates its own Secret from the `apiKey` value. For ArgoCD, the API key is provided via the pre-created `resume-tailor-api-key` Kubernetes Secret. The Helm chart's deployment reads the key from `envFrom` on the secret created by the chart.

To use the externally-created secret instead of the Helm-managed one, you can override the Helm values in `application.yaml` or configure the deployment to reference `resume-tailor-api-key` directly.

## Useful ArgoCD commands

```bash
# Check sync status
argocd app get resume-tailor

# Force a sync
argocd app sync resume-tailor

# View app history
argocd app history resume-tailor

# Open the ArgoCD UI
kubectl port-forward svc/argocd-server -n argocd 8080:443
# Then visit https://localhost:8080
```
