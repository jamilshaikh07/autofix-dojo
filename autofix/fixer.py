"""Fix suggestion engine for determining safe image updates."""

import logging
import re
from typing import NamedTuple

from .models import Finding, FixSuggestion

logger = logging.getLogger(__name__)


class SemVer(NamedTuple):
    """Semantic version representation."""

    major: int
    minor: int
    patch: int
    prerelease: str = ""

    def __str__(self) -> str:
        base = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            return f"{base}-{self.prerelease}"
        return base


def parse_semver(version: str) -> SemVer | None:
    """Parse a version string into SemVer components."""
    # Handle common version patterns
    pattern = r"^v?(\d+)\.(\d+)\.(\d+)(?:-(.+))?$"
    match = re.match(pattern, version)

    if not match:
        # Try major.minor only
        pattern_minor = r"^v?(\d+)\.(\d+)$"
        match = re.match(pattern_minor, version)
        if match:
            return SemVer(int(match.group(1)), int(match.group(2)), 0)
        return None

    return SemVer(
        major=int(match.group(1)),
        minor=int(match.group(2)),
        patch=int(match.group(3)),
        prerelease=match.group(4) or "",
    )


# Known safe version mappings for common images (hackathon simulation)
KNOWN_SAFE_VERSIONS: dict[str, dict[str, str]] = {
    "nginx": {
        "1.23.1": "1.23.4",
        "1.23.2": "1.23.4",
        "1.23.3": "1.23.4",
        "1.24.0": "1.24.0",
        "1.25.0": "1.25.4",
        "1.25.1": "1.25.4",
    },
    "python": {
        "3.9.0": "3.9.18",
        "3.10.0": "3.10.13",
        "3.11.0": "3.11.7",
    },
    "node": {
        "18.0.0": "18.19.0",
        "20.0.0": "20.10.0",
    },
    "redis": {
        "7.0.0": "7.0.14",
        "7.2.0": "7.2.4",
    },
    "postgres": {
        "15.0": "15.5",
        "16.0": "16.1",
    },
}


def suggest_new_image_tag(current_tag: str, image_name: str = "") -> str | None:
    """
    Suggest a safe newer tag for the given image.

    For MVP: Uses known mappings or increments patch version.

    Args:
        current_tag: Current version tag (e.g., "1.23.1")
        image_name: Base image name (e.g., "nginx")

    Returns:
        Suggested new tag or None if no suggestion available.
    """
    # Extract base image name from full path
    base_name = image_name.split("/")[-1].split(":")[0]

    # Check known safe versions first
    if base_name in KNOWN_SAFE_VERSIONS:
        known = KNOWN_SAFE_VERSIONS[base_name]
        if current_tag in known:
            return known[current_tag]

    # Try to increment patch version
    semver = parse_semver(current_tag)
    if semver:
        # Increment patch by 3 (simulating available security patch)
        new_version = SemVer(
            major=semver.major,
            minor=semver.minor,
            patch=semver.patch + 3,
            prerelease="",  # Remove prerelease for stability
        )
        return str(new_version)

    return None


def generate_fix_suggestions(findings: list[Finding]) -> list[FixSuggestion]:
    """
    Generate fix suggestions for a list of findings.

    Args:
        findings: List of vulnerability findings.

    Returns:
        List of fix suggestions (one per unique image).
    """
    suggestions = []
    seen_images: set[str] = set()

    for finding in findings:
        if not finding.component_name or not finding.component_version:
            continue

        image_key = f"{finding.component_name}:{finding.component_version}"
        if image_key in seen_images:
            continue

        suggested_tag = suggest_new_image_tag(
            finding.component_version,
            finding.component_name,
        )

        if suggested_tag and suggested_tag != finding.component_version:
            suggestion = FixSuggestion(
                finding_id=finding.id,
                current_image=finding.component_name,
                current_tag=finding.component_version,
                suggested_tag=suggested_tag,
                confidence="high" if finding.component_name.split("/")[-1] in KNOWN_SAFE_VERSIONS else "medium",
                reason=f"Bump from {finding.component_version} to {suggested_tag} to address {finding.severity.value} vulnerability",
            )
            suggestions.append(suggestion)
            seen_images.add(image_key)

    logger.info(f"Generated {len(suggestions)} fix suggestions")
    return suggestions


def is_patch_safe(current: str, suggested: str) -> bool:
    """
    Check if the suggested version is a safe patch update.

    Safe updates:
    - Same major and minor version
    - Patch version is higher
    """
    current_ver = parse_semver(current)
    suggested_ver = parse_semver(suggested)

    if not current_ver or not suggested_ver:
        return False

    return (
        current_ver.major == suggested_ver.major
        and current_ver.minor == suggested_ver.minor
        and suggested_ver.patch > current_ver.patch
    )
