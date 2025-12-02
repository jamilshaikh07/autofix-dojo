"""Tests for DefectDojo client."""

import pytest

from autofix.dojo_client import group_findings_by_image
from autofix.models import Finding, Severity


def test_group_findings_by_image_single():
    """Test grouping with single finding."""
    findings = [
        Finding(
            id=1,
            title="CVE-2023-1234",
            severity=Severity.HIGH,
            component_name="nginx",
            component_version="1.23.1",
        )
    ]

    grouped = group_findings_by_image(findings)

    assert len(grouped) == 1
    assert "nginx:1.23.1" in grouped
    assert len(grouped["nginx:1.23.1"]) == 1


def test_group_findings_by_image_multiple_same_image():
    """Test grouping multiple findings for same image."""
    findings = [
        Finding(
            id=1,
            title="CVE-2023-1234",
            severity=Severity.HIGH,
            component_name="nginx",
            component_version="1.23.1",
        ),
        Finding(
            id=2,
            title="CVE-2023-5678",
            severity=Severity.CRITICAL,
            component_name="nginx",
            component_version="1.23.1",
        ),
    ]

    grouped = group_findings_by_image(findings)

    assert len(grouped) == 1
    assert len(grouped["nginx:1.23.1"]) == 2


def test_group_findings_by_image_different_images():
    """Test grouping findings for different images."""
    findings = [
        Finding(
            id=1,
            title="CVE-2023-1234",
            severity=Severity.HIGH,
            component_name="nginx",
            component_version="1.23.1",
        ),
        Finding(
            id=2,
            title="CVE-2023-5678",
            severity=Severity.HIGH,
            component_name="redis",
            component_version="7.0.0",
        ),
    ]

    grouped = group_findings_by_image(findings)

    assert len(grouped) == 2
    assert "nginx:1.23.1" in grouped
    assert "redis:7.0.0" in grouped


def test_group_findings_no_version():
    """Test grouping findings without version info."""
    findings = [
        Finding(
            id=1,
            title="CVE-2023-1234",
            severity=Severity.HIGH,
            component_name="myapp",
            component_version=None,
        ),
    ]

    grouped = group_findings_by_image(findings)

    assert len(grouped) == 1
    assert "myapp" in grouped
