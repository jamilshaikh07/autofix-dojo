"""Helm chart scanner for detecting outdated releases in Terraform, ArgoCD, and cluster."""

import json
import logging
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import yaml

logger = logging.getLogger(__name__)


@dataclass
class HelmRelease:
    """Represents a Helm release found in Terraform or cluster."""

    name: str
    chart: str
    repository: str
    current_version: str
    latest_version: str | None = None
    namespace: str = "default"
    source_file: str | None = None
    source_line: int | None = None
    app_version: str | None = None
    latest_app_version: str | None = None

    @property
    def is_outdated(self) -> bool:
        """Check if release is outdated."""
        if not self.latest_version:
            return False
        return self.current_version != self.latest_version

    @property
    def version_gap(self) -> int:
        """Calculate major version gap."""
        if not self.latest_version:
            return 0
        try:
            current_major = int(self.current_version.lstrip("v").split(".")[0])
            latest_major = int(self.latest_version.lstrip("v").split(".")[0])
            return latest_major - current_major
        except (ValueError, IndexError):
            return 0

    @property
    def priority(self) -> str:
        """Determine upgrade priority based on version gap."""
        gap = self.version_gap
        if gap >= 3:
            return "critical"
        elif gap >= 1:
            return "major"
        elif self.is_outdated:
            return "minor"
        return "current"

    @property
    def priority_emoji(self) -> str:
        """Get emoji for priority."""
        return {
            "critical": "🔴",
            "major": "🟠",
            "minor": "🟡",
            "current": "✅",
        }.get(self.priority, "⚪")


class HelmScanner:
    """Scanner for Helm releases in Terraform files and Kubernetes clusters."""

    # Known Helm repositories
    KNOWN_REPOS = {
        # Infrastructure
        "https://kubernetes.github.io/autoscaler": "autoscaler",
        "https://projectcalico.docs.tigera.io/charts": "calico",
        "https://kubernetes-sigs.github.io/metrics-server/": "metrics-server",
        "https://kubernetes.github.io/ingress-nginx": "ingress-nginx",
        # Monitoring & Observability
        "https://grafana.github.io/helm-charts": "grafana",
        "https://prometheus-community.github.io/helm-charts": "prometheus-community",
        # GitOps & CI/CD
        "https://argoproj.github.io/argo-helm": "argo",
        # Storage
        "https://charts.longhorn.io": "longhorn",
        "https://charts.min.io/": "minio",
        # Networking
        "https://helm.cilium.io/": "cilium",
        "https://metallb.github.io/metallb": "metallb",
        "https://traefik.github.io/charts": "traefik",
        # Security & Certificates
        "https://charts.jetstack.io": "jetstack",
        # Backup
        "https://vmware-tanzu.github.io/helm-charts": "vmware-tanzu",
        # Database
        "https://opensource.zalando.com/postgres-operator/charts/postgres-operator": "zalando",
        # Cloud providers
        "https://aws.github.io/eks-charts": "eks",
        "https://sumologic.github.io/sumologic-kubernetes-collection": "sumologic",
        "https://mtougeron.github.io/helm-charts": "k8s-pvc-tagger",
        # Other common charts
        "https://nfs-subdir-external-provisioner.github.io/nfs-subdir-external-provisioner": "nfs-provisioner",
    }

    def __init__(self):
        self._repo_cache: dict[str, list[dict]] = {}
        self._repos_initialized = False

    def _init_repos(self) -> None:
        """Initialize all known Helm repositories."""
        if self._repos_initialized:
            return

        logger.info("Initializing Helm repositories...")
        for repo_url, repo_name in self.KNOWN_REPOS.items():
            try:
                result = subprocess.run(
                    ["helm", "repo", "add", repo_name, repo_url],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.returncode != 0 and "already exists" not in result.stderr:
                    logger.debug(f"Failed to add repo {repo_name}: {result.stderr}")
            except Exception as e:
                logger.debug(f"Failed to add repo {repo_name}: {e}")

        # Update all repos
        try:
            subprocess.run(["helm", "repo", "update"], capture_output=True, check=False)
        except Exception:
            pass

        self._repos_initialized = True

    def scan_terraform_dir(self, path: str | Path) -> list[HelmRelease]:
        """Scan a directory for Terraform helm_release resources."""
        path = Path(path)
        releases = []

        for tf_file in path.rglob("*.tf"):
            releases.extend(self._parse_terraform_file(tf_file))

        # Fetch latest versions
        for release in releases:
            self._fetch_latest_version(release)

        return releases

    def _parse_terraform_file(self, file_path: Path) -> Iterator[HelmRelease]:
        """Parse a Terraform file for helm_release resources."""
        content = file_path.read_text()

        # Regex pattern for helm_release blocks
        pattern = r'resource\s+"helm_release"\s+"([^"]+)"\s*\{([^}]+(?:\{[^}]*\}[^}]*)*)\}'

        for match in re.finditer(pattern, content, re.DOTALL):
            resource_name = match.group(1)
            block_content = match.group(2)
            block_start = match.start()

            # Calculate line number
            line_number = content[:block_start].count("\n") + 1

            # Extract attributes
            name = self._extract_attr(block_content, "name") or resource_name
            chart = self._extract_attr(block_content, "chart") or ""
            repository = self._extract_attr(block_content, "repository") or ""
            version = self._extract_attr(block_content, "version") or ""
            namespace = self._extract_attr(block_content, "namespace") or "default"

            if chart and version:
                yield HelmRelease(
                    name=name,
                    chart=chart,
                    repository=repository,
                    current_version=version,
                    namespace=namespace,
                    source_file=str(file_path),
                    source_line=line_number,
                )

    def _extract_attr(self, block: str, attr: str) -> str | None:
        """Extract an attribute value from a Terraform block."""
        # Match: attribute = "value" or attribute = var.something
        pattern = rf'{attr}\s*=\s*"([^"]*)"'
        match = re.search(pattern, block)
        if match:
            return match.group(1)

        # Try without quotes (for variables)
        pattern = rf'{attr}\s*=\s*(\S+)'
        match = re.search(pattern, block)
        if match:
            value = match.group(1)
            if not value.startswith(("var.", "local.", "data.")):
                return value
        return None

    def _fetch_latest_version(self, release: HelmRelease) -> None:
        """Fetch the latest version from Helm repository."""
        if not release.repository:
            return

        # Initialize repos on first use
        self._init_repos()

        repo_alias = self.KNOWN_REPOS.get(release.repository)
        if not repo_alias:
            # Try to add repo dynamically
            repo_alias = release.name.replace("-", "_")
            try:
                subprocess.run(
                    ["helm", "repo", "add", repo_alias, release.repository],
                    capture_output=True,
                    check=False,
                )
            except Exception:
                return

        try:
            result = subprocess.run(
                ["helm", "search", "repo", f"{repo_alias}/{release.chart}", "--output", "json"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                charts = json.loads(result.stdout)
                if charts:
                    release.latest_version = charts[0].get("version")
                    release.latest_app_version = charts[0].get("app_version")
        except Exception as e:
            logger.warning(f"Failed to fetch latest version for {release.chart}: {e}")

    def scan_argocd_apps(self, path: str | Path) -> list[HelmRelease]:
        """Scan ArgoCD Application YAML files for Helm chart sources."""
        path = Path(path)
        releases = []

        # Find all YAML files
        yaml_files = list(path.rglob("*.yaml")) + list(path.rglob("*.yml"))

        for yaml_file in yaml_files:
            try:
                content = yaml_file.read_text()
                # Handle multi-document YAML
                for doc in yaml.safe_load_all(content):
                    if not doc:
                        continue
                    releases.extend(self._parse_argocd_app(doc, yaml_file))
            except Exception as e:
                logger.warning(f"Failed to parse {yaml_file}: {e}")

        # Fetch latest versions
        for release in releases:
            self._fetch_latest_version(release)

        return releases

    def _parse_argocd_app(self, doc: dict, source_file: Path) -> Iterator[HelmRelease]:
        """Parse an ArgoCD Application document for Helm sources."""
        if doc.get("kind") != "Application":
            return

        api_version = doc.get("apiVersion", "")
        if not api_version.startswith("argoproj.io/"):
            return

        metadata = doc.get("metadata", {})
        app_name = metadata.get("name", "unknown")

        spec = doc.get("spec", {})
        destination = spec.get("destination", {})
        namespace = destination.get("namespace", "default")

        # Handle single source
        source = spec.get("source", {})
        if source:
            release = self._extract_helm_from_source(source, app_name, namespace, source_file)
            if release:
                yield release

        # Handle multiple sources (sources array)
        sources = spec.get("sources", [])
        for source in sources:
            release = self._extract_helm_from_source(source, app_name, namespace, source_file)
            if release:
                yield release

    def _extract_helm_from_source(
        self, source: dict, app_name: str, namespace: str, source_file: Path
    ) -> HelmRelease | None:
        """Extract Helm release info from an ArgoCD source."""
        chart = source.get("chart")
        repo_url = source.get("repoURL", "")
        target_revision = source.get("targetRevision", "")

        # Only process Helm chart sources (not Git path sources)
        if not chart:
            return None

        return HelmRelease(
            name=app_name,
            chart=chart,
            repository=repo_url,
            current_version=target_revision,
            namespace=namespace,
            source_file=str(source_file),
        )

    def scan_cluster(self, kubeconfig: str | None = None) -> list[HelmRelease]:
        """Scan a Kubernetes cluster for installed Helm releases."""
        releases = []
        cmd = ["helm", "list", "--all-namespaces", "--output", "json"]

        env = None
        if kubeconfig:
            import os
            env = os.environ.copy()
            env["KUBECONFIG"] = kubeconfig

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, env=env)
            helm_releases = json.loads(result.stdout)

            for hr in helm_releases:
                release = HelmRelease(
                    name=hr.get("name", ""),
                    chart=hr.get("chart", "").rsplit("-", 1)[0],  # Remove version suffix
                    repository="",  # Not available from helm list
                    current_version=hr.get("chart", "").rsplit("-", 1)[-1] if "-" in hr.get("chart", "") else "",
                    namespace=hr.get("namespace", "default"),
                    app_version=hr.get("app_version"),
                )
                releases.append(release)

        except Exception as e:
            logger.error(f"Failed to list Helm releases: {e}")

        return releases

    def generate_report(self, releases: list[HelmRelease]) -> str:
        """Generate a markdown report of Helm releases."""
        lines = [
            "# Helm Release Scan Report\n",
            "## Summary\n",
        ]

        # Count by priority
        counts = {"critical": 0, "major": 0, "minor": 0, "current": 0}
        for r in releases:
            counts[r.priority] += 1

        lines.append(f"| Priority | Count |")
        lines.append(f"|----------|-------|")
        lines.append(f"| 🔴 Critical | {counts['critical']} |")
        lines.append(f"| 🟠 Major | {counts['major']} |")
        lines.append(f"| 🟡 Minor | {counts['minor']} |")
        lines.append(f"| ✅ Current | {counts['current']} |")
        lines.append("")

        # Detailed table
        lines.append("## Releases\n")
        lines.append("| Status | Chart | Current | Latest | Namespace | Source |")
        lines.append("|--------|-------|---------|--------|-----------|--------|")

        for r in sorted(releases, key=lambda x: ({"critical": 0, "major": 1, "minor": 2, "current": 3}[x.priority], x.name)):
            source = f"`{Path(r.source_file).name}:{r.source_line}`" if r.source_file else "-"
            latest = r.latest_version or "?"
            lines.append(f"| {r.priority_emoji} | {r.chart} | {r.current_version} | {latest} | {r.namespace} | {source} |")

        return "\n".join(lines)
