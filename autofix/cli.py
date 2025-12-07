"""CLI entrypoint for autofix-dojo."""

import logging
import subprocess
import sys
from pathlib import Path

import typer

from .config import Config
from .dojo_client import DojoClient, group_findings_by_image
from .fixer import generate_fix_suggestions
from .git_client import GitClient, apply_fix
from .helm.scanner import HelmScanner
from .helm.roadmap import generate_roadmap
from .slo_tracker import SLOTracker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = typer.Typer(
    name="autofix-dojo",
    help="Autonomous Vulnerability Fixer for DefectDojo + Kubernetes",
)


@app.command()
def scan_and_fix(
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Show what would be done without making changes",
    ),
    severity: list[str] = typer.Option(
        ["Critical", "High"],
        "--severity",
        "-s",
        help="Severity levels to process",
    ),
) -> None:
    """Fetch findings from DefectDojo, generate fixes, and create PRs."""
    try:
        config = Config.from_env()
    except ValueError as e:
        typer.echo(f"Configuration error: {e}", err=True)
        raise typer.Exit(1)

    typer.echo("🔍 Connecting to DefectDojo...")
    dojo_client = DojoClient(config)
    git_client = GitClient(config)
    slo_tracker = SLOTracker(config)

    # Fetch findings
    typer.echo(f"📥 Fetching open {', '.join(severity)} findings...")
    findings = dojo_client.fetch_open_findings(severity)

    if not findings:
        typer.echo("✅ No open findings found!")
        return

    typer.echo(f"Found {len(findings)} open findings")

    # Group by image
    grouped = group_findings_by_image(findings)
    typer.echo(f"Grouped into {len(grouped)} unique images/components")

    # Generate fix suggestions
    typer.echo("🔧 Generating fix suggestions...")
    suggestions = generate_fix_suggestions(findings)

    if not suggestions:
        typer.echo("⚠️  No auto-fixable vulnerabilities found")
        return

    typer.echo(f"Generated {len(suggestions)} fix suggestions:")
    for s in suggestions:
        typer.echo(f"  • {s.current_image}: {s.current_tag} → {s.suggested_tag}")

    if dry_run:
        typer.echo("\n🏃 Dry run mode - no changes made")
        return

    # Start SLO tracking
    slo_tracker.start_run(
        total_findings=len(findings),
        auto_fixable=len(suggestions),
    )

    # Apply fixes
    typer.echo("\n🚀 Applying fixes...")
    success_count = 0

    for suggestion in suggestions:
        typer.echo(f"\nProcessing: {suggestion.full_current_image}...")
        result = apply_fix(git_client, suggestion)

        if result.success:
            typer.echo(f"  ✅ PR created: {result.pr_url}")
            slo_tracker.record_fix(result.pr_url or "")
            success_count += 1
        else:
            typer.echo(f"  ❌ Failed: {result.error}")

    # Complete SLO tracking
    record = slo_tracker.complete_run()

    # Summary
    typer.echo("\n" + "=" * 50)
    typer.echo("📊 Summary")
    typer.echo("=" * 50)
    typer.echo(f"Total findings:    {len(findings)}")
    typer.echo(f"Auto-fixable:      {len(suggestions)}")
    typer.echo(f"Successfully fixed: {success_count}")
    if record:
        typer.echo(f"SLO:               {record.slo_percentage:.1f}%")


@app.command()
def show_slo() -> None:
    """Display SLO summary and statistics."""
    try:
        config = Config.from_env()
    except ValueError as e:
        typer.echo(f"Configuration error: {e}", err=True)
        raise typer.Exit(1)

    slo_tracker = SLOTracker(config)
    summary = slo_tracker.get_summary()

    typer.echo("=" * 50)
    typer.echo("📊 Vulnerability SLO Summary")
    typer.echo("=" * 50)
    typer.echo(f"Total runs:              {summary['total_runs']}")
    typer.echo(f"Total findings processed: {summary['total_findings_processed']}")
    typer.echo(f"Total auto-fixed:         {summary['total_auto_fixed']}")
    typer.echo(f"Average SLO:              {summary['average_slo']:.1f}%")
    typer.echo(f"Latest SLO:               {summary['latest_slo']:.1f}%")

    # Show recent history
    history = slo_tracker.get_history(5)
    if history:
        typer.echo("\n📈 Recent Runs:")
        for record in reversed(history):
            typer.echo(
                f"  {record.timestamp[:19]}: "
                f"{record.auto_fixed}/{record.total_findings} fixed "
                f"({record.slo_percentage:.1f}%)"
            )


@app.command()
def smoke_test(
    deployment: str = typer.Argument(..., help="Deployment name"),
    namespace: str = typer.Option("default", "--namespace", "-n", help="Kubernetes namespace"),
) -> None:
    """Run a smoke test to verify deployment rollout status."""
    typer.echo(f"🔄 Checking rollout status for {deployment} in {namespace}...")

    result = subprocess.run(
        ["kubectl", "rollout", "status", f"deploy/{deployment}", "-n", namespace],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        typer.echo(f"✅ Deployment {deployment} is healthy")
        typer.echo(result.stdout)
    else:
        typer.echo(f"❌ Deployment {deployment} rollout issue:")
        typer.echo(result.stderr or result.stdout)
        raise typer.Exit(1)


@app.command()
def list_findings(
    severity: list[str] = typer.Option(
        ["Critical", "High"],
        "--severity",
        "-s",
        help="Severity levels to filter",
    ),
    limit: int = typer.Option(20, "--limit", "-l", help="Max findings to show"),
) -> None:
    """List open findings from DefectDojo."""
    try:
        config = Config.from_env()
    except ValueError as e:
        typer.echo(f"Configuration error: {e}", err=True)
        raise typer.Exit(1)

    dojo_client = DojoClient(config)
    findings = dojo_client.fetch_open_findings(severity)

    if not findings:
        typer.echo("No open findings found")
        return

    typer.echo(f"Found {len(findings)} open findings:\n")

    for finding in findings[:limit]:
        severity_icon = "🔴" if finding.severity.value == "Critical" else "🟠"
        typer.echo(f"{severity_icon} [{finding.severity.value}] {finding.title}")
        if finding.image_tag:
            typer.echo(f"   Image: {finding.image_tag}")
        typer.echo(f"   ID: {finding.id}")
        typer.echo()

    if len(findings) > limit:
        typer.echo(f"... and {len(findings) - limit} more")


@app.command()
def scan_helm(
    path: str = typer.Argument(
        ".",
        help="Path to scan for Helm charts (Terraform or ArgoCD apps)",
    ),
    source_type: str = typer.Option(
        "auto",
        "--type",
        "-t",
        help="Source type: terraform, argocd, cluster, or auto (detect)",
    ),
    output: str = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file for markdown report",
    ),
    kubeconfig: str = typer.Option(
        None,
        "--kubeconfig",
        "-k",
        help="Path to kubeconfig for cluster scanning",
    ),
) -> None:
    """Scan for outdated Helm charts in Terraform, ArgoCD apps, or cluster."""
    scanner = HelmScanner()
    releases = []

    # Auto-detect source type
    if source_type == "auto":
        path_obj = Path(path)
        if any(path_obj.rglob("*.tf")):
            source_type = "terraform"
        elif any(path_obj.rglob("*.yaml")) or any(path_obj.rglob("*.yml")):
            source_type = "argocd"
        else:
            source_type = "cluster"

    if source_type == "terraform":
        typer.echo(f"🔍 Scanning Terraform files in {path}...")
        releases = scanner.scan_terraform_dir(path)
    elif source_type == "argocd":
        typer.echo(f"🔍 Scanning ArgoCD Application manifests in {path}...")
        releases = scanner.scan_argocd_apps(path)
    elif source_type == "cluster":
        typer.echo(f"🔍 Scanning Kubernetes cluster for Helm releases...")
        releases = scanner.scan_cluster(kubeconfig)

    if not releases:
        typer.echo("No helm_release resources found")
        return

    # Summary
    outdated = [r for r in releases if r.is_outdated]
    critical = [r for r in releases if r.priority == "critical"]
    major = [r for r in releases if r.priority == "major"]

    typer.echo(f"\n📊 Found {len(releases)} Helm releases:")
    typer.echo(f"   🔴 Critical: {len(critical)}")
    typer.echo(f"   🟠 Major:    {len(major)}")
    typer.echo(f"   🟡 Minor:    {len([r for r in releases if r.priority == 'minor'])}")
    typer.echo(f"   ✅ Current:  {len([r for r in releases if r.priority == 'current'])}")

    typer.echo("\n" + "=" * 70)
    typer.echo(f"{'Chart':<30} {'Current':<12} {'Latest':<12} {'Status':<10}")
    typer.echo("=" * 70)

    for r in sorted(releases, key=lambda x: (
        {"critical": 0, "major": 1, "minor": 2, "current": 3}[x.priority],
        x.name
    )):
        latest = r.latest_version or "?"
        typer.echo(f"{r.priority_emoji} {r.chart:<28} {r.current_version:<12} {latest:<12}")

    # Generate report
    if output:
        report = scanner.generate_report(releases)
        Path(output).write_text(report)
        typer.echo(f"\n📄 Report saved to {output}")

    # Show critical upgrade paths
    if critical:
        typer.echo("\n" + "=" * 70)
        typer.echo("🚨 CRITICAL UPGRADES REQUIRED")
        typer.echo("=" * 70)
        for r in critical:
            typer.echo(f"\n{r.chart}: {r.current_version} → {r.latest_version}")
            typer.echo(f"   Run: autofix-dojo helm-roadmap {r.chart} {r.current_version} {r.latest_version}")


@app.command()
def helm_roadmap(
    chart: str = typer.Argument(..., help="Helm chart name"),
    current: str = typer.Argument(..., help="Current version"),
    target: str = typer.Argument(..., help="Target version"),
    output: str = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file for markdown roadmap",
    ),
) -> None:
    """Generate upgrade roadmap for a Helm chart."""
    typer.echo(f"📋 Generating upgrade roadmap for {chart}...")
    typer.echo(f"   {current} → {target}")

    roadmap = generate_roadmap(chart, current, target)

    typer.echo(f"\n{'=' * 60}")
    typer.echo(f"📍 Upgrade Path: {len(roadmap.steps)} steps")
    typer.echo(f"⏱️  Estimated Time: {roadmap.estimated_time_minutes} minutes")
    typer.echo(f"⚠️  Breaking Changes: {roadmap.total_breaking_changes}")
    typer.echo(f"{'=' * 60}")

    # Show path
    path_str = " → ".join([current] + [s.to_version for s in roadmap.steps])
    typer.echo(f"\n{path_str}\n")

    for i, step in enumerate(roadmap.steps, 1):
        typer.echo(f"Step {i}: {step.from_version} → {step.to_version} [{step.risk_emoji} {step.risk.upper()}]")
        if step.breaking_changes:
            for bc in step.breaking_changes:
                typer.echo(f"   ⚠️  {bc}")
        if step.notes:
            typer.echo(f"   📝 {step.notes}")

    if output:
        Path(output).write_text(roadmap.to_markdown())
        typer.echo(f"\n📄 Roadmap saved to {output}")


@app.command()
def scan_images(
    kubeconfig: str = typer.Option(
        None,
        "--kubeconfig",
        "-k",
        help="Path to kubeconfig file",
    ),
    namespace: str = typer.Option(
        None,
        "--namespace",
        "-n",
        help="Namespace to scan (default: all)",
    ),
    output: str = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file for report",
    ),
) -> None:
    """Scan Kubernetes cluster for container images and versions."""
    import json
    import os

    typer.echo("🔍 Scanning cluster for container images...")

    # Build kubectl command
    cmd = ["kubectl", "get", "deployments,statefulsets,daemonsets"]
    if namespace:
        cmd.extend(["-n", namespace])
    else:
        cmd.append("-A")
    cmd.extend(["-o", "json"])

    env = os.environ.copy()
    if kubeconfig:
        env["KUBECONFIG"] = kubeconfig

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, env=env)
        data = json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        typer.echo(f"❌ Failed to get resources: {e.stderr}", err=True)
        raise typer.Exit(1)
    except json.JSONDecodeError as e:
        typer.echo(f"❌ Failed to parse response: {e}", err=True)
        raise typer.Exit(1)

    # Extract images
    images: dict[str, list[dict]] = {}
    for item in data.get("items", []):
        metadata = item.get("metadata", {})
        ns = metadata.get("namespace", "default")
        name = metadata.get("name", "unknown")
        kind = item.get("kind", "Unknown")

        containers = item.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
        for container in containers:
            image = container.get("image", "")
            if image:
                if image not in images:
                    images[image] = []
                images[image].append({
                    "namespace": ns,
                    "name": name,
                    "kind": kind,
                    "container": container.get("name", ""),
                })

    if not images:
        typer.echo("No container images found")
        return

    # Parse and categorize images
    typer.echo(f"\n📊 Found {len(images)} unique images across {sum(len(v) for v in images.values())} workloads")
    typer.echo("\n" + "=" * 80)
    typer.echo(f"{'Image':<60} {'Workloads':<10}")
    typer.echo("=" * 80)

    # Sort by number of workloads using the image
    for image, workloads in sorted(images.items(), key=lambda x: -len(x[1])):
        # Truncate long image names
        display_image = image if len(image) <= 58 else "..." + image[-55:]
        typer.echo(f"{display_image:<60} {len(workloads):<10}")

    # Show images that might need updates (with version tags)
    typer.echo("\n" + "=" * 80)
    typer.echo("🔎 Images with explicit version tags (potential update candidates):")
    typer.echo("=" * 80)

    import re
    version_pattern = re.compile(r":v?\d+\.\d+")

    for image in sorted(images.keys()):
        if version_pattern.search(image) and ":latest" not in image:
            # Parse image:tag
            parts = image.rsplit(":", 1)
            if len(parts) == 2:
                img_name, tag = parts
                workload_count = len(images[image])
                typer.echo(f"  {img_name}")
                typer.echo(f"    Current: {tag} (used by {workload_count} workload(s))")

    if output:
        report_lines = ["# Cluster Image Scan Report\n"]
        report_lines.append(f"Total unique images: {len(images)}\n")
        report_lines.append("| Image | Tag | Workloads |")
        report_lines.append("|-------|-----|-----------|")
        for image, workloads in sorted(images.items()):
            parts = image.rsplit(":", 1)
            img_name = parts[0]
            tag = parts[1] if len(parts) == 2 else "latest"
            report_lines.append(f"| {img_name} | {tag} | {len(workloads)} |")
        Path(output).write_text("\n".join(report_lines))
        typer.echo(f"\n📄 Report saved to {output}")


def _get_next_major_version(current: str, latest: str, all_versions: list[str]) -> str:
    """Find the next major version step between current and latest.

    For example: 4.3.0 -> 11.2.0 with all versions would return 5.x.x (first 5.x version)
    """
    import re

    def parse_version(v: str) -> tuple[int, int, int]:
        """Parse version string to tuple, handling 'v' prefix."""
        v = v.lstrip("v")
        parts = re.split(r"[.\-]", v)
        try:
            return (int(parts[0]), int(parts[1]) if len(parts) > 1 else 0, int(parts[2]) if len(parts) > 2 else 0)
        except (ValueError, IndexError):
            return (0, 0, 0)

    current_parsed = parse_version(current)
    latest_parsed = parse_version(latest)

    # If same major version, return latest
    if current_parsed[0] == latest_parsed[0]:
        return latest

    # Find the highest version of the next major
    next_major = current_parsed[0] + 1
    target_major = latest_parsed[0]

    # Filter versions that are in the next major range
    next_major_versions = []
    for v in all_versions:
        parsed = parse_version(v)
        if parsed[0] == next_major:
            next_major_versions.append((parsed, v))

    if next_major_versions:
        # Return the highest version of next major
        next_major_versions.sort(reverse=True)
        return next_major_versions[0][1]

    # If no versions found for next major, try to find any version > current but < latest
    # This handles cases where major versions are skipped (e.g., no v9.x)
    intermediate_versions = []
    for v in all_versions:
        parsed = parse_version(v)
        if current_parsed < parsed < latest_parsed:
            intermediate_versions.append((parsed, v))

    if intermediate_versions:
        intermediate_versions.sort()
        # Return the first version after current (smallest step)
        return intermediate_versions[0][1]

    # Fallback to latest
    return latest


@app.command()
def helm_upgrade_pr(
    path: str = typer.Argument(
        ".",
        help="Path to scan for Helm charts (ArgoCD apps or Terraform)",
    ),
    chart: str = typer.Option(
        None,
        "--chart",
        "-c",
        help="Specific chart to upgrade (default: all outdated)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Show what would be done without making changes",
    ),
    priority: str = typer.Option(
        "major",
        "--priority",
        "-p",
        help="Minimum priority: critical, major, minor, or all",
    ),
    step: bool = typer.Option(
        True,
        "--step/--no-step",
        help="Upgrade one major version at a time (default: True for safe upgrades)",
    ),
    batch: bool = typer.Option(
        True,
        "--batch/--no-batch",
        help="Create one PR per priority level instead of per chart (default: True)",
    ),
) -> None:
    """Scan for outdated Helm charts and create PRs for upgrades.

    By default, creates batched PRs - one per priority level (critical, major, minor).
    Use --no-batch to create individual PRs per chart.
    """
    import os
    import re
    import subprocess
    from collections import defaultdict

    # Validate Git configuration
    git_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GIT_TOKEN")
    repo_url = os.environ.get("GIT_REPO_URL")

    if not git_token:
        typer.echo("❌ GITHUB_TOKEN or GIT_TOKEN environment variable required", err=True)
        raise typer.Exit(1)

    if not repo_url:
        typer.echo("❌ GIT_REPO_URL environment variable required", err=True)
        raise typer.Exit(1)

    scanner = HelmScanner()

    # Scan for charts
    typer.echo(f"🔍 Scanning for Helm charts in {path}...")
    path_obj = Path(path)

    if any(path_obj.rglob("*.tf")):
        releases = scanner.scan_terraform_dir(path)
    else:
        releases = scanner.scan_argocd_apps(path)

    if not releases:
        typer.echo("No Helm charts found")
        return

    # Debug: show all found releases
    typer.echo(f"📊 Found {len(releases)} total Helm releases")
    for r in releases:
        typer.echo(f"   - {r.chart}: {r.current_version} → {r.latest_version or '?'} (priority: {r.priority}, outdated: {r.is_outdated})")

    # Filter by priority
    priority_levels = {"critical": 0, "major": 1, "minor": 2, "all": 3}
    min_priority = priority_levels.get(priority, 1)

    candidates = []
    for r in releases:
        r_priority = {"critical": 0, "major": 1, "minor": 2, "current": 4}.get(r.priority, 3)
        if r_priority <= min_priority and r.is_outdated:
            if chart is None or r.chart == chart or r.name == chart:
                candidates.append(r)

    if not candidates:
        typer.echo("✅ No charts need upgrading at the specified priority level")
        return

    typer.echo(f"\n📋 Found {len(candidates)} chart(s) to upgrade:")
    for r in candidates:
        typer.echo(f"   {r.priority_emoji} {r.chart}: {r.current_version} → {r.latest_version}")

    if dry_run:
        typer.echo("\n🏃 Dry run mode - no changes made")
        return

    # Find git root first (needed for all operations)
    first_release = candidates[0]
    source_path = Path(first_release.source_file)

    git_root_result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, cwd=source_path.parent
    )
    if git_root_result.returncode != 0:
        typer.echo("❌ Not a git repository")
        raise typer.Exit(1)

    git_root = Path(git_root_result.stdout.strip())

    # Process step mode for critical upgrades (version_gap > 1)
    processed_releases = []
    for release in candidates:
        old_version = release.current_version
        new_version = release.latest_version

        if step and release.version_gap > 1:
            typer.echo(f"\n📊 {release.chart}: Step mode - fetching all versions...")
            all_versions = scanner.fetch_all_versions(release)
            if all_versions:
                new_version = _get_next_major_version(old_version, release.latest_version, all_versions)
                if new_version != release.latest_version:
                    typer.echo(f"   🔄 Step: {old_version} → {new_version} (toward {release.latest_version})")

        processed_releases.append((release, old_version, new_version))

    if batch:
        # Batch mode: Group by priority and create one PR per priority
        _create_batched_prs(processed_releases, git_root, scanner, step)
    else:
        # Individual mode: Create one PR per chart
        _create_individual_prs(processed_releases, git_root, scanner, step)


def _create_batched_prs(
    processed_releases: list,
    git_root: Path,
    scanner,
    step: bool,
) -> None:
    """Create one PR per priority level containing all upgrades of that priority."""
    import re
    import subprocess
    from collections import defaultdict

    # Group releases by priority
    by_priority: dict[str, list] = defaultdict(list)
    for release, old_version, new_version in processed_releases:
        by_priority[release.priority].append((release, old_version, new_version))

    typer.echo("\n🚀 Creating batched upgrade PRs...")

    success_count = 0
    priority_order = ["critical", "major", "minor"]

    for priority_level in priority_order:
        if priority_level not in by_priority:
            continue

        releases_in_batch = by_priority[priority_level]
        if not releases_in_batch:
            continue

        typer.echo(f"\n📦 Processing {priority_level.upper()} upgrades ({len(releases_in_batch)} charts)...")

        # Ensure we're on the main branch
        subprocess.run(["git", "checkout", "master"], cwd=git_root, capture_output=True)
        subprocess.run(["git", "pull", "origin", "master"], cwd=git_root, capture_output=True)

        # Create a branch name based on priority
        branch_name = f"autofix/helm-{priority_level}-upgrades"
        typer.echo(f"   Creating branch: {branch_name}")

        # Delete branch if it exists locally
        subprocess.run(["git", "branch", "-D", branch_name], cwd=git_root, capture_output=True)

        # Create new branch
        subprocess.run(["git", "checkout", "-b", branch_name], cwd=git_root, capture_output=True)

        # Track changes for PR description
        changes = []
        files_changed = []

        for release, old_version, new_version in releases_in_batch:
            source_path = Path(release.source_file)
            if not source_path.is_absolute():
                source_path = git_root / source_path

            if not source_path.exists():
                typer.echo(f"   ⚠️  Skipping {release.chart}: file not found")
                continue

            content = source_path.read_text()

            # Pattern for version = "x.y.z" (Terraform)
            tf_pattern = rf'(version\s*=\s*["\'])({re.escape(old_version)})(["\'])'
            tf_replacement = rf'\g<1>{new_version}\g<3>'

            # Pattern for targetRevision: vx.y.z or x.y.z (ArgoCD)
            argocd_pattern = rf'(targetRevision:\s*["\']?v?)({re.escape(old_version)})(["\']?)'
            argocd_replacement = rf'\g<1>{new_version}\g<3>'

            new_content = re.sub(tf_pattern, tf_replacement, content)
            if new_content == content:
                new_content = re.sub(argocd_pattern, argocd_replacement, content)

            if new_content == content:
                typer.echo(f"   ⚠️  Skipping {release.chart}: version pattern not found")
                continue

            # Write the changes
            source_path.write_text(new_content)

            relative_path = source_path.relative_to(git_root)
            files_changed.append(str(relative_path))

            # Track for PR description
            is_step = step and new_version != release.latest_version
            if is_step:
                changes.append(f"- **{release.chart}**: {old_version} → {new_version} (step toward {release.latest_version})")
            else:
                changes.append(f"- **{release.chart}**: {old_version} → {new_version}")

            typer.echo(f"   ✓ {release.chart}: {old_version} → {new_version}")

        if not changes:
            typer.echo(f"   ⚠️  No changes to commit for {priority_level}")
            subprocess.run(["git", "checkout", "master"], cwd=git_root, capture_output=True)
            continue

        # Stage and commit all changes
        for f in files_changed:
            subprocess.run(["git", "add", f], cwd=git_root, capture_output=True)

        commit_msg = f"chore(helm): {priority_level} upgrades - {len(changes)} charts"
        subprocess.run(["git", "commit", "-m", commit_msg], cwd=git_root, capture_output=True)

        # Push
        push_result = subprocess.run(
            ["git", "push", "-u", "origin", branch_name, "--force"],
            cwd=git_root, capture_output=True, text=True
        )

        if push_result.returncode != 0:
            typer.echo(f"   ❌ Failed to push: {push_result.stderr}")
            subprocess.run(["git", "checkout", "master"], cwd=git_root, capture_output=True)
            continue

        # Create PR
        emoji_map = {"critical": "🔴", "major": "🟠", "minor": "🟡"}
        emoji = emoji_map.get(priority_level, "📦")

        pr_title = f"{emoji} chore(helm): {priority_level} upgrades ({len(changes)} charts)"

        pr_body = f"""## {priority_level.title()} Helm Chart Upgrades

This PR contains **{len(changes)} {priority_level} upgrade(s)**.

### Changes
{chr(10).join(changes)}

### Files Modified
{chr(10).join([f"- `{f}`" for f in files_changed])}

### Upgrade Priority
- 🔴 **Critical**: 3+ major versions behind
- 🟠 **Major**: 1-2 major versions behind
- 🟡 **Minor**: Patch/minor version updates

---
🤖 Generated by autofix-dojo
"""

        pr_result = subprocess.run(
            ["gh", "pr", "create", "--title", pr_title, "--body", pr_body, "--head", branch_name],
            cwd=git_root, capture_output=True, text=True
        )

        # Return to main branch
        subprocess.run(["git", "checkout", "master"], cwd=git_root, capture_output=True)

        if pr_result.returncode == 0:
            pr_url = pr_result.stdout.strip()
            typer.echo(f"   ✅ PR created: {pr_url}")
            success_count += 1
        else:
            typer.echo(f"   ⚠️  PR creation failed: {pr_result.stderr}")
            typer.echo(f"   Branch '{branch_name}' is ready for manual PR creation")

    typer.echo("\n" + "=" * 50)
    typer.echo(f"📊 Created {success_count} batched PR(s)")


def _create_individual_prs(
    processed_releases: list,
    git_root: Path,
    scanner,
    step: bool,
) -> None:
    """Create one PR per chart (original behavior)."""
    import re
    import subprocess

    typer.echo("\n🚀 Creating individual upgrade PRs...")

    success_count = 0
    for release, old_version, new_version in processed_releases:
        typer.echo(f"\nProcessing {release.chart}...")

        source_path = Path(release.source_file)
        if not source_path.is_absolute():
            source_path = git_root / source_path

        if not source_path.exists():
            typer.echo(f"   ⚠️  Source file not found: {source_path}")
            continue

        content = source_path.read_text()

        # Pattern for version = "x.y.z" (Terraform)
        tf_pattern = rf'(version\s*=\s*["\'])({re.escape(old_version)})(["\'])'
        tf_replacement = rf'\g<1>{new_version}\g<3>'

        # Pattern for targetRevision: vx.y.z or x.y.z (ArgoCD)
        argocd_pattern = rf'(targetRevision:\s*["\']?v?)({re.escape(old_version)})(["\']?)'
        argocd_replacement = rf'\g<1>{new_version}\g<3>'

        new_content = re.sub(tf_pattern, tf_replacement, content)
        if new_content == content:
            new_content = re.sub(argocd_pattern, argocd_replacement, content)

        if new_content == content:
            typer.echo(f"   ⚠️  Could not find version to update")
            continue

        # Ensure we're on main branch
        subprocess.run(["git", "checkout", "master"], cwd=git_root, capture_output=True)
        subprocess.run(["git", "pull", "origin", "master"], cwd=git_root, capture_output=True)

        branch_name = f"autofix/helm-upgrade-{release.chart}-{new_version}".replace(".", "-")
        typer.echo(f"   Creating branch: {branch_name}")

        # Delete if exists
        subprocess.run(["git", "branch", "-D", branch_name], cwd=git_root, capture_output=True)
        subprocess.run(["git", "checkout", "-b", branch_name], cwd=git_root, capture_output=True)

        # Write and commit
        source_path.write_text(new_content)
        relative_path = source_path.relative_to(git_root)
        subprocess.run(["git", "add", str(relative_path)], cwd=git_root, capture_output=True)

        commit_msg = f"chore(helm): upgrade {release.chart} from {old_version} to {new_version}"
        subprocess.run(["git", "commit", "-m", commit_msg], cwd=git_root, capture_output=True)

        # Push
        push_result = subprocess.run(
            ["git", "push", "-u", "origin", branch_name, "--force"],
            cwd=git_root, capture_output=True, text=True
        )

        if push_result.returncode != 0:
            typer.echo(f"   ❌ Failed to push: {push_result.stderr}")
            subprocess.run(["git", "checkout", "master"], cwd=git_root, capture_output=True)
            continue

        # Create PR
        is_step_upgrade = step and new_version != release.latest_version
        pr_title = f"chore(helm): upgrade {release.chart} to {new_version}"
        if is_step_upgrade:
            pr_title += f" (step toward {release.latest_version})"

        step_info = ""
        if is_step_upgrade:
            step_info = f"""
### Step Upgrade
- Current: {old_version}
- This PR: {new_version}
- Target: {release.latest_version}
"""

        pr_body = f"""## Helm Chart Upgrade

**Chart:** {release.chart}
**Priority:** {release.priority_emoji} {release.priority}
**Version:** {old_version} → {new_version}
{step_info}
### Changes
- Updated `{relative_path}`

---
🤖 Generated by autofix-dojo
"""

        pr_result = subprocess.run(
            ["gh", "pr", "create", "--title", pr_title, "--body", pr_body, "--head", branch_name],
            cwd=git_root, capture_output=True, text=True
        )

        subprocess.run(["git", "checkout", "master"], cwd=git_root, capture_output=True)

        if pr_result.returncode == 0:
            pr_url = pr_result.stdout.strip()
            typer.echo(f"   ✅ PR created: {pr_url}")
            success_count += 1
        else:
            typer.echo(f"   ⚠️  PR creation failed: {pr_result.stderr}")

    typer.echo("\n" + "=" * 50)
    typer.echo(f"📊 Created {success_count}/{len(processed_releases)} upgrade PRs")


@app.command()
def version() -> None:
    """Show autofix-dojo version."""
    typer.echo("autofix-dojo v0.2.0")
    typer.echo("Autonomous Vulnerability & Helm Chart Fixer")
    typer.echo("https://github.com/jamilshaikh07/autofix-dojo")


def main() -> None:
    """Main entrypoint."""
    app()


if __name__ == "__main__":
    main()
