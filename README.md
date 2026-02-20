# autofix-dojo

> Autonomous vulnerability remediation & Helm chart upgrade automation for Kubernetes. Fix CVEs and keep your Helm charts up-to-date while you sleep.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![DefectDojo](https://img.shields.io/badge/DefectDojo-Compatible-green.svg)](https://www.defectdojo.com/)
[![Helm](https://img.shields.io/badge/Helm-Charts-blue.svg)](https://helm.sh/)

**autofix-dojo** is a GitOps-native automation tool that:
- Connects to DefectDojo to identify vulnerable container images and creates PRs to fix them
- Scans your Helm charts for outdated versions and creates step-by-step upgrade PRs (like Dependabot for Helm!)
- Provides a web dashboard for manual job triggering and monitoring
- Exposes Prometheus metrics for Grafana dashboards

## Features

### Vulnerability Remediation
- **DefectDojo Integration** - Fetch Critical/High findings via REST API
- **Smart Image Versioning** - Suggests safe patch-level updates using semver logic
- **Kubernetes-Native** - Updates Deployments, Helm values, and YAML manifests
- **Git Automation** - Creates branches, commits, and PRs via `gh`/`glab` CLI
- **SLO Tracking** - Measures auto-fix success rate over time

### Helm Chart Upgrades (Dependabot for Helm)
- **ArgoCD App Scanning** - Scans ArgoCD Application manifests for Helm charts
- **Version Detection** - Compares current vs latest versions from Helm repos
- **Step-by-Step Upgrades** - Creates sequential PRs for major version jumps (e.g., v1 → v2 → v3)
- **Priority-Based Batching** - Groups upgrades by priority (critical, major, minor)
- **Safe Automation** - One PR at a time to prevent breaking changes

### Web Dashboard & Observability
- **Web UI** - Real-time dashboard with quick action buttons
- **Manual Job Triggering** - Trigger scans and upgrades on-demand
- **Prometheus Metrics** - `/metrics` endpoint for Grafana dashboards
- **CronJob Status** - View job history and logs

### General
- **Dry-Run Mode** - Preview changes without modifying anything
- **GitHub & GitLab Support** - Works with both platforms out of the box
- **Kubernetes CronJob Mode** - Run as scheduled jobs in your cluster

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   DefectDojo    │────▶│   autofix-dojo   │────▶│   Git (GitHub/  │
│   (Findings)    │     │                  │     │     GitLab)     │
└─────────────────┘     └────────┬─────────┘     └────────┬────────┘
                                 │                        │
                                 │                        ▼
                        ┌────────▼─────────┐     ┌─────────────────┐
                        │  K8s Manifests/  │     │     ArgoCD      │
                        │   Helm Values    │     │   (GitOps Sync) │
                        └──────────────────┘     └─────────────────┘
```

## How It Works

### Vulnerability Remediation Flow
1. **Fetch** - Queries DefectDojo API for open Critical/High vulnerabilities
2. **Analyze** - Groups findings by container image and determines fix candidates
3. **Suggest** - Uses known-safe mappings or semver patch bumps to suggest updates
4. **Update** - Modifies Kubernetes manifests and Helm values in your GitOps repo
5. **PR** - Creates a pull request with detailed change summary
6. **Track** - Records SLO metrics for compliance reporting

### Helm Chart Upgrade Flow
1. **Scan** - Parses ArgoCD Application manifests for Helm chart references
2. **Compare** - Queries Helm repos for latest versions
3. **Prioritize** - Categorizes updates as critical, major, or minor
4. **Step** - For major jumps, creates sequential PRs (v1→v2, then v2→v3)
5. **PR** - Creates batched PRs grouped by priority level
6. **Wait** - Monitors for PR merge before creating next upgrade PR

## Working Demo

Successfully tested against a homelab Kubernetes cluster:

- **PR Created**: [talos-proxmox-gitops#3](https://github.com/jamilshaikh07/talos-proxmox-gitops/pull/3)
- **Fix Applied**: `nginx:1.23.1` → `nginx:1.23.4`
- **SLO Tracked**: 25% (1 of 4 findings auto-fixed)

### Sample Output

```
🔍 Connecting to DefectDojo...
📥 Fetching open Critical, High findings...
Found 4 open findings
Grouped into 4 unique images/components
🔧 Generating fix suggestions...
Generated 3 fix suggestions:
  • nginx: 1.23.1 → 1.23.4
  • redis: 7.0.0 → 7.0.14
  • python: 3.11.0 → 3.11.7

🚀 Applying fixes...
Processing: nginx:1.23.1...
  ✅ PR created: https://github.com/jamilshaikh07/talos-proxmox-gitops/pull/3

==================================================
📊 Summary
==================================================
Total findings:    4
Auto-fixable:      3
Successfully fixed: 1
SLO:               25.0%
```

## Quick Start

```bash
# Clone the repository
git clone https://github.com/jamilshaikh07/autofix-dojo.git
cd autofix-dojo

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your values

# Seed DefectDojo with test data (optional)
python scripts/seed_dojo.py

# Run in dry-run mode first
python -m autofix.cli scan-and-fix --dry-run

# Run for real
python -m autofix.cli scan-and-fix
```

## Requirements

- Python 3.11+
- Git
- GitHub CLI (`gh`) or GitLab CLI (`glab`)
- Access to a DefectDojo instance
- A GitOps repository with Kubernetes manifests

## Configuration

Create a `.env` file or set environment variables:

```bash
# DefectDojo
DEFECTDOJO_URL=https://defectdojo.example.com
DEFECTDOJO_API_KEY=your-api-key-here
DEFECTDOJO_PRODUCT_ID=1

# Git
GIT_REPO_PATH=/path/to/your/k8s-manifests
GIT_REMOTE=origin
GIT_MAIN_BRANCH=main
GIT_PLATFORM=github  # or gitlab

# ArgoCD (optional)
ARGO_ENABLED=false

# SLO Tracking
SLO_DB_PATH=slo_data.json
```

### Getting a DefectDojo API Key

```bash
# If using Docker Compose DefectDojo
docker exec django-defectdojo-uwsgi-1 python /app/manage.py shell -c "
from dojo.models import Dojo_User
from rest_framework.authtoken.models import Token
user = Dojo_User.objects.get(username='admin')
token, created = Token.objects.get_or_create(user=user)
print(f'API_KEY={token.key}')
"
```

## CLI Commands

### Vulnerability Scanning (DefectDojo)

```bash
# Scan and auto-fix vulnerabilities
python -m autofix.cli scan-and-fix
python -m autofix.cli scan-and-fix --dry-run
python -m autofix.cli scan-and-fix --severity Critical

# List open findings
python -m autofix.cli list-findings
python -m autofix.cli list-findings --severity Critical --limit 50

# View SLO metrics
python -m autofix.cli show-slo

# Smoke test a deployment
python -m autofix.cli smoke-test my-deployment -n my-namespace
```

### Helm Chart Upgrades

```bash
# Scan for outdated Helm charts
python -m autofix.cli helm-scan \
  --repo-owner jamilshaikh07 \
  --repo-name talos-proxmox-gitops \
  --scan-path gitops/apps

# Create PRs for outdated charts (batched by priority)
python -m autofix.cli helm-upgrade-pr \
  --repo-owner jamilshaikh07 \
  --repo-name talos-proxmox-gitops \
  --scan-path gitops/apps \
  --priority minor  # Creates PRs for minor, major, and critical

# Dry run (no PRs created)
python -m autofix.cli helm-upgrade-pr \
  --repo-owner jamilshaikh07 \
  --repo-name talos-proxmox-gitops \
  --scan-path gitops/apps \
  --dry-run
```

### Manual Job Triggering (Kubernetes)

```bash
# Using the CLI (from inside the cluster or with kubectl exec)
python -m autofix.cli trigger helm-upgrade-pr -n autofix-dojo
python -m autofix.cli trigger helm-scan -n autofix-dojo
python -m autofix.cli trigger vuln-scan -n autofix-dojo

# Wait for job completion
python -m autofix.cli trigger helm-upgrade-pr -n autofix-dojo --wait
```

### Using kubectl Directly

```bash
# Trigger helm-upgrade-pr job from CronJob
kubectl create job --from=cronjob/autofix-dojo-helm-upgrade-pr helm-upgrade-pr-manual-$(date +%s) -n autofix-dojo

# Trigger helm-scan job from CronJob
kubectl create job --from=cronjob/autofix-dojo-helm-scan helm-scan-manual-$(date +%s) -n autofix-dojo

# Trigger vuln-scan job from CronJob
kubectl create job --from=cronjob/autofix-dojo-vuln-scan vuln-scan-manual-$(date +%s) -n autofix-dojo

# Watch job progress
kubectl get jobs -n autofix-dojo -w

# View logs of a running/completed job
kubectl logs job/helm-upgrade-pr-manual-1234567890 -n autofix-dojo --follow

# Delete completed jobs
kubectl delete jobs -n autofix-dojo --field-selector status.successful=1
```

### Web Dashboard

```bash
# Start the web dashboard locally
python -m autofix.cli web --host 0.0.0.0 --port 8080

# With auto-reload for development
python -m autofix.cli web --reload
```

## Docker

```bash
# Build
docker build -t autofix-dojo .

# Run
docker run --rm \
  -v /path/to/manifests:/manifests \
  -v ~/.gitconfig:/home/autofix/.gitconfig:ro \
  -e DEFECTDOJO_URL=https://dojo.example.com \
  -e DEFECTDOJO_API_KEY=xxx \
  -e GIT_REPO_PATH=/manifests \
  autofix-dojo scan-and-fix --dry-run
```

## Project Structure

```
autofix-dojo/
├── autofix/
│   ├── __init__.py
│   ├── cli.py           # Typer CLI commands (all commands + PR helpers)
│   ├── config.py        # Environment variable loading
│   ├── dojo_client.py   # DefectDojo REST API client
│   ├── fixer.py         # Version parsing and fix suggestions
│   ├── git_client.py    # Git operations and PR creation (gh/glab)
│   ├── models.py        # Dataclasses (Finding, FixSuggestion, etc.)
│   ├── slo_tracker.py   # JSON-based SLO tracking
│   ├── helm/
│   │   ├── scanner.py   # HelmRelease + HelmScanner (Terraform/ArgoCD/cluster)
│   │   └── roadmap.py   # Multi-major upgrade roadmap generation
│   └── web/
│       └── app.py       # FastAPI web dashboard + Prometheus metrics
├── deploy/
│   ├── helm-chart/      # Helm chart for Kubernetes deployment
│   │   ├── templates/
│   │   │   ├── deployment-web.yaml
│   │   │   ├── service-web.yaml
│   │   │   ├── ingress-web.yaml
│   │   │   ├── cronjob-helm-scan.yaml
│   │   │   ├── cronjob-helm-upgrade-pr.yaml
│   │   │   ├── cronjob-vuln-scan.yaml
│   │   │   ├── rbac.yaml
│   │   │   └── servicemonitor.yaml
│   │   ├── examples/
│   │   │   ├── values-homelab.yaml
│   │   │   ├── values-aws-eks.yaml
│   │   │   └── values-cronjob-only.yaml
│   │   └── values.yaml
│   └── grafana/
│       └── dashboard.json  # Grafana dashboard
├── scripts/
│   └── seed_dojo.py     # Seed DefectDojo with test data
├── tests/
├── Dockerfile
├── .env.example
├── requirements.txt
└── README.md
```

## Known Safe Versions

The fixer includes mappings for common images:

| Image | Vulnerable Versions | Safe Version |
|-------|---------------------|--------------|
| nginx | 1.23.1, 1.23.2, 1.23.3 | 1.23.4 |
| python | 3.9.0, 3.10.0, 3.11.0 | 3.9.18, 3.10.13, 3.11.7 |
| redis | 7.0.0, 7.2.0 | 7.0.14, 7.2.4 |
| postgres | 15.0, 16.0 | 15.5, 16.1 |
| node | 18.0.0, 20.0.0 | 18.19.0, 20.10.0 |

For unknown versions, the fixer increments the patch version by 3.

## Vulnerability SLO

The service tracks a simple SLO metric:

```
SLO % = (auto_fixed_findings / total_findings) * 100
```

This measures what percentage of HIGH/CRITICAL vulnerabilities were automatically remediated via PRs. Use `show-slo` to view historical trends.

## Kubernetes Deployment

### Using Helm

```bash
# Add the Helm repository (if published)
helm repo add autofix-dojo https://jamilshaikh07.github.io/autofix-dojo

# Install with custom values
helm install autofix-dojo autofix-dojo/autofix-dojo \
  --namespace autofix-dojo \
  --create-namespace \
  --set web.enabled=true \
  --set web.ingress.enabled=true \
  --set web.ingress.hosts[0].host=autofix.example.com \
  --set metrics.enabled=true \
  --set metrics.serviceMonitor.enabled=true
```

### Using ArgoCD

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: autofix-dojo
  namespace: argocd
spec:
  destination:
    namespace: autofix-dojo
    server: https://kubernetes.default.svc
  project: default
  source:
    repoURL: https://github.com/jamilshaikh07/autofix-dojo
    path: deploy/helm-chart
    targetRevision: master
    helm:
      values: |
        image:
          repository: ghcr.io/jamilshaikh07/autofix-dojo
          tag: "master"
        web:
          enabled: true
          ingress:
            enabled: true
            className: "nginx"
            hosts:
              - host: autofix.example.com
                paths:
                  - path: /
                    pathType: Prefix
        metrics:
          enabled: true
          serviceMonitor:
            enabled: true
        helm:
          enabled: true
          autoPR:
            enabled: true
            schedule: "0 0 * * 1"  # Weekly
            repoOwner: "your-org"
            repoName: "your-gitops-repo"
            scanPath: "gitops/apps"
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

## Web Dashboard

The web dashboard provides:

- **Quick Actions** - One-click buttons to trigger jobs
- **CronJob Status** - View all scheduled jobs and their next run time
- **Job History** - List of recent job runs with status
- **Log Viewer** - Real-time logs from running jobs
- **Health Check** - `/api/health` endpoint for liveness/readiness probes

### Endpoints

| Endpoint | Description |
|----------|-------------|
| `/` | Web dashboard UI |
| `/api/health` | Health check (JSON) |
| `/api/cronjobs` | List CronJobs |
| `/api/jobs` | List Jobs |
| `/api/trigger` | Trigger a job (POST) |
| `/api/logs/{pod}` | Get pod logs |
| `/metrics` | Prometheus metrics |

### Prometheus Metrics

The `/metrics` endpoint exposes:

- `autofix_jobs_triggered_total` - Counter of triggered jobs by type
- `autofix_helm_charts_outdated` - Gauge of outdated charts by priority
- `autofix_helm_scan_duration_seconds` - Histogram of scan duration

## Roadmap

| Version | Milestone | Status |
|---------|-----------|--------|
| v0.1 | MVP - DefectDojo + GitHub PRs | Done |
| v0.2 | Improved fixer logic, registry lookups | Done |
| v0.3 | GitLab MR support | Done |
| v0.4 | ArgoCD sync integration | Done |
| v0.5 | Kubernetes CronJob mode | Done |
| v0.6 | Helm chart upgrade automation | Done |
| v0.7 | Web dashboard + Prometheus metrics | Done |
| v1.0 | InfraOps Autonomous Engine | In Progress |

## Homelab Deployment

Currently running on a Talos Linux / Proxmox cluster:

- **Namespace**: `autofix-dojo`
- **GitOps repo**: `github.com/jamilshaikh07/talos-proxmox-gitops`
- **Scan path**: `gitops/apps/` (ArgoCD Application manifests)
- **Storage**: Longhorn PVC for SLO data
- **Schedule**: Weekly on Monday (`0 0 * * 1`) for Helm jobs

```bash
# Connect to homelab cluster
export KUBECONFIG=~/.kube/config-homelab

# Check status
kubectl get all -n autofix-dojo

# View web dashboard logs
kubectl logs -n autofix-dojo deployment/autofix-dojo-web --tail=50

# Manually trigger jobs
kubectl create job --from=cronjob/autofix-dojo-helm-upgrade-pr helm-upgrade-pr-manual-$(date +%s) -n autofix-dojo
kubectl create job --from=cronjob/autofix-dojo-helm-scan helm-scan-manual-$(date +%s) -n autofix-dojo
```

## Why Open Source?

Security automation shouldn't be locked behind enterprise paywalls. By open-sourcing autofix-dojo, we aim to:

- Give every team access to vulnerability auto-remediation
- Build a community around autonomous InfraOps
- Learn from real-world usage patterns
- Accelerate the path to fully autonomous infrastructure

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.

---
