# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**autofix-dojo** is a GitOps-native automation tool (v0.2.0) that:
1. Queries DefectDojo for Critical/High CVEs and creates PRs to bump vulnerable container image versions
2. Scans ArgoCD Application manifests for outdated Helm charts and creates step-by-step upgrade PRs (Dependabot for Helm)
3. Serves a FastAPI web dashboard for manual job triggering and Prometheus metrics

It is deployed on a homelab Talos Linux / Kubernetes cluster (namespace: `autofix-dojo`). The kubeconfig is at `~/.kube/config-homelab`.

## Development Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e ".[dev]"   # includes pytest, pytest-cov
cp .env.example .env      # set DEFECTDOJO_URL, DEFECTDOJO_API_KEY, GIT_REPO_PATH, etc.
```

## Common Commands

```bash
# Run all tests
pytest tests/

# Run a single test file
pytest tests/test_fixer.py -v

# Run with coverage
pytest tests/ --cov=autofix --cov-report=term-missing

# CLI (module invocation)
python -m autofix.cli --help
python -m autofix.cli scan-and-fix --dry-run
python -m autofix.cli helm-upgrade-pr . --dry-run
python -m autofix.cli helm-scan . --type argocd
python -m autofix.cli web --reload   # local dev dashboard at :8080

# Seed DefectDojo with test data
python scripts/seed_dojo.py

# Helm chart lint
helm lint deploy/helm-chart/
helm template autofix-dojo deploy/helm-chart/ -f deploy/helm-chart/examples/values-homelab.yaml
```

## Cluster Operations (homelab)

```bash
export KUBECONFIG=~/.kube/config-homelab

# View all resources
kubectl get all -n autofix-dojo

# Web dashboard logs (running deployment)
kubectl logs -n autofix-dojo deployment/autofix-dojo-web --tail=100

# Manually trigger a CronJob
kubectl create job --from=cronjob/autofix-dojo-helm-upgrade-pr helm-upgrade-pr-manual-$(date +%s) -n autofix-dojo
kubectl create job --from=cronjob/autofix-dojo-helm-scan helm-scan-manual-$(date +%s) -n autofix-dojo

# Follow job logs
kubectl logs -f job/<job-name> -n autofix-dojo

# Deploy/upgrade via Helm
helm upgrade --install autofix-dojo deploy/helm-chart/ \
  --namespace autofix-dojo \
  -f deploy/helm-chart/examples/values-homelab.yaml \
  --set image.tag=master
```

## Architecture

### Request Flow

```
CLI command / Web UI
      ↓
autofix/cli.py          ← Typer CLI, all command definitions live here
      ↓
autofix/config.py       ← Loads env vars into Config dataclass
      ↓
┌─────────────────────────────────────────┐
│  Vulnerability flow    │  Helm flow     │
│  dojo_client.py        │  helm/scanner.py│
│  fixer.py              │  helm/roadmap.py│
│  git_client.py         │  cli.py helpers │
└─────────────────────────────────────────┘
      ↓
git_client.py           ← git + gh/glab CLI to create PRs
slo_tracker.py          ← JSON-backed SLO metrics (/data/slo_data.json)
```

### Key Module Responsibilities

| Module | Role |
|--------|------|
| `autofix/cli.py` | All CLI commands (1089 lines). Also contains `_create_batched_prs` and `_create_individual_prs` helpers inlined — not in separate files. |
| `autofix/config.py` | `Config.from_env()` — reads env vars, raises `ValueError` if `DEFECTDOJO_URL`/`DEFECTDOJO_API_KEY` missing |
| `autofix/dojo_client.py` | REST calls to DefectDojo API with pagination; `group_findings_by_image()` groups by image name |
| `autofix/fixer.py` | Semver logic + known-safe version mappings for nginx/python/redis/postgres/node; patch-bumps unknown versions by 3 |
| `autofix/git_client.py` | Wraps `git` and `gh`/`glab` CLI; platform selected via `config.git_platform` |
| `autofix/helm/scanner.py` | `HelmRelease` dataclass + `HelmScanner` class; scans Terraform HCL, ArgoCD YAML, or live cluster; fetches latest versions from Helm repos |
| `autofix/helm/roadmap.py` | Generates step-by-step upgrade roadmaps for multi-major-version jumps |
| `autofix/web/app.py` | FastAPI app; uses `subprocess`/`kubectl` directly for job control; Prometheus metrics at `/metrics`; health at `/api/health` |
| `autofix/models.py` | `Finding`, `FixSuggestion`, `FixResult`, `SLORecord` dataclasses + `Severity` enum |
| `autofix/slo_tracker.py` | Appends JSON records to `SLO_DB_PATH`; `start_run` / `record_fix` / `complete_run` lifecycle |

### Helm Upgrade Priority System

`HelmRelease.priority` is computed from major version gap:
- `critical` → gap ≥ 3 major versions
- `major` → gap 1-2 major versions
- `minor` → outdated within same major
- `current` → up to date

Step mode (`--step`, default on) upgrades one major version at a time. Batched mode (`--batch`, default on) creates one PR per priority level (`autofix/helm-critical-upgrades`, `autofix/helm-major-upgrades`, `autofix/helm-minor-upgrades`).

### Kubernetes Deployment Layout

```
deploy/helm-chart/
├── templates/
│   ├── deployment-web.yaml          # Web dashboard Deployment
│   ├── cronjob-helm-scan.yaml       # Weekly Helm version scan
│   ├── cronjob-helm-upgrade-pr.yaml # Weekly PR creator (init: git-clone, main: helm-upgrade-pr)
│   ├── cronjob-vuln-scan.yaml       # Every 6h DefectDojo scan (only when defectdojo.enabled)
│   ├── rbac.yaml                    # ClusterRole for Job/Pod/log access
│   └── servicemonitor.yaml          # Prometheus Operator scrape target
├── examples/
│   └── values-homelab.yaml          # Homelab-specific (Talos, Longhorn, defectdojo disabled)
└── values.yaml
```

The `helm-upgrade-pr` CronJob uses an init container (`alpine/git`) to clone the GitOps repo before the main container runs.

### Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `DEFECTDOJO_URL` | Yes (vuln flow) | — | DefectDojo base URL |
| `DEFECTDOJO_API_KEY` | Yes (vuln flow) | — | API token |
| `DEFECTDOJO_PRODUCT_ID` | No | None | Filter by product |
| `GIT_REPO_PATH` | No | `.` | Local path to GitOps repo |
| `GIT_PLATFORM` | No | `github` | `github` or `gitlab` |
| `GIT_MAIN_BRANCH` | No | `main` | Base branch for PRs |
| `GITHUB_TOKEN` / `GIT_TOKEN` | Yes (helm-upgrade-pr) | — | For `gh` CLI auth |
| `GIT_REPO_URL` | Yes (helm-upgrade-pr) | — | Repo to clone in CronJob |
| `SLO_DB_PATH` | No | `slo_data.json` | SLO tracking file |

## CI/CD

GitHub Actions (`.github/workflows/docker-publish.yaml`):
- **build-and-push**: multi-platform Docker image → `ghcr.io/jamilshaikh07/autofix-dojo`
- **helm-lint**: `helm lint` + `helm template`
- **test**: `pytest` + codecov

Image tags: branch name, PR number, semver (`major.minor`, full), short SHA.

## Homelab Context

- Cluster: Talos Linux on Proxmox
- GitOps repo: `github.com/jamilshaikh07/talos-proxmox-gitops`
- ArgoCD app manifests scanned at: `gitops/apps/`
- Active upgrade PRs: #12 (critical), #13 (major), #14 (minor) — already exist, re-runs skip PR creation gracefully
- Storage: Longhorn (`storageClass: longhorn`) for SLO PVC
- Web dashboard: `deployment/autofix-dojo-web`, liveness/readiness on `/api/health`
- CronJobs schedule: weekly on Monday (`0 0 * * 1`)
