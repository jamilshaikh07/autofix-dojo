# Roadmap

The journey from MVP to autonomous InfraOps engine.

## v0.1 - MVP (Current)

- [x] DefectDojo API integration
- [x] Basic image version bumping
- [x] GitHub PR creation
- [x] SLO tracking
- [x] CLI interface
- [x] Docker support

## v0.2 - Improved Fixer Logic

- [ ] Container registry API lookups (Docker Hub, GHCR, ECR)
- [ ] Validate suggested versions actually exist
- [ ] Support for digest-based image references
- [ ] Configurable fix strategies (patch-only, minor, latest)
- [ ] CVE-to-fixed-version database integration

## v0.3 - GitLab Support

- [ ] Full GitLab MR workflow
- [ ] GitLab CI integration examples
- [ ] Self-hosted GitLab compatibility
- [ ] Merge request approval workflows

## v0.4 - ArgoCD Integration

- [ ] Trigger ArgoCD sync after PR merge
- [ ] ArgoCD Application health checks
- [ ] Rollback on failed deployments
- [ ] Sync wave support for ordered updates

## v0.5 - Kubernetes CronJob Mode

- [ ] Helm chart for deployment
- [ ] CronJob-based scheduled runs
- [ ] ConfigMap/Secret configuration
- [ ] Prometheus metrics endpoint
- [ ] Grafana dashboard templates

## v0.6 - Operator Version

- [ ] Custom Resource Definition (CRD): `AutofixPolicy`
- [ ] Kubernetes Operator pattern
- [ ] Per-namespace/per-app policies
- [ ] Event-driven remediation
- [ ] Admission webhook for prevention

## v1.0 - InfraOps Autonomous Engine

- [ ] Multi-cluster support
- [ ] Policy-as-code (OPA/Rego integration)
- [ ] AI-assisted fix suggestions
- [ ] Blast radius analysis
- [ ] Automated rollback triggers
- [ ] Compliance reporting (SOC2, PCI-DSS)
- [ ] Web dashboard
- [ ] Slack/Teams notifications
- [ ] Audit logging

---

## Beyond v1.0

- Terraform/OpenTofu module remediation
- Cloud provider native integrations (AWS Security Hub, GCP SCC)
- SBOM generation and tracking
- Supply chain security (Sigstore/cosign)
- Multi-tenant SaaS offering

---

Want to help shape this roadmap? [Open a discussion](https://github.com/jamilshaikh07/autofix-dojo/discussions)!
