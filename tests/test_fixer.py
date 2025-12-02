"""Tests for fix suggestion engine."""

import pytest

from autofix.fixer import (
    SemVer,
    generate_fix_suggestions,
    is_patch_safe,
    parse_semver,
    suggest_new_image_tag,
)
from autofix.models import Finding, Severity


class TestParseSemver:
    """Tests for semver parsing."""

    def test_parse_standard_version(self):
        result = parse_semver("1.23.4")
        assert result == SemVer(1, 23, 4, "")

    def test_parse_with_v_prefix(self):
        result = parse_semver("v1.23.4")
        assert result == SemVer(1, 23, 4, "")

    def test_parse_with_prerelease(self):
        result = parse_semver("1.0.0-alpha")
        assert result == SemVer(1, 0, 0, "alpha")

    def test_parse_major_minor_only(self):
        result = parse_semver("15.0")
        assert result == SemVer(15, 0, 0, "")

    def test_parse_invalid(self):
        result = parse_semver("latest")
        assert result is None


class TestSuggestNewImageTag:
    """Tests for image tag suggestions."""

    def test_known_nginx_version(self):
        result = suggest_new_image_tag("1.23.1", "nginx")
        assert result == "1.23.4"

    def test_known_redis_version(self):
        result = suggest_new_image_tag("7.0.0", "redis")
        assert result == "7.0.14"

    def test_unknown_image_patch_increment(self):
        result = suggest_new_image_tag("2.0.0", "unknown-image")
        assert result == "2.0.3"

    def test_full_image_path(self):
        result = suggest_new_image_tag("1.23.1", "docker.io/library/nginx")
        assert result == "1.23.4"


class TestIsPatchSafe:
    """Tests for patch safety check."""

    def test_safe_patch_bump(self):
        assert is_patch_safe("1.23.1", "1.23.4") is True

    def test_unsafe_minor_bump(self):
        assert is_patch_safe("1.23.1", "1.24.0") is False

    def test_unsafe_major_bump(self):
        assert is_patch_safe("1.23.1", "2.0.0") is False

    def test_same_version(self):
        assert is_patch_safe("1.23.1", "1.23.1") is False


class TestGenerateFixSuggestions:
    """Tests for generating fix suggestions."""

    def test_generate_for_known_image(self):
        findings = [
            Finding(
                id=1,
                title="CVE-2023-1234",
                severity=Severity.HIGH,
                component_name="nginx",
                component_version="1.23.1",
            )
        ]

        suggestions = generate_fix_suggestions(findings)

        assert len(suggestions) == 1
        assert suggestions[0].current_tag == "1.23.1"
        assert suggestions[0].suggested_tag == "1.23.4"
        assert suggestions[0].confidence == "high"

    def test_no_duplicates_for_same_image(self):
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

        suggestions = generate_fix_suggestions(findings)

        assert len(suggestions) == 1

    def test_no_suggestion_without_component(self):
        findings = [
            Finding(
                id=1,
                title="Generic vulnerability",
                severity=Severity.HIGH,
                component_name=None,
                component_version=None,
            )
        ]

        suggestions = generate_fix_suggestions(findings)

        assert len(suggestions) == 0
