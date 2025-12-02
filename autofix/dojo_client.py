"""DefectDojo API client for fetching vulnerability findings."""

import logging
from typing import Iterator

import requests

from .config import Config
from .models import Finding, Severity

logger = logging.getLogger(__name__)


class DojoClient:
    """Client for interacting with DefectDojo REST API."""

    def __init__(self, config: Config):
        self.config = config
        self.base_url = config.defectdojo_url
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Token {config.defectdojo_api_key}",
            "Content-Type": "application/json",
        })

    def _get_paginated(self, endpoint: str, params: dict | None = None) -> Iterator[dict]:
        """Fetch all pages from a paginated endpoint."""
        url = f"{self.base_url}/api/v2/{endpoint}"
        params = params or {}
        params.setdefault("limit", 100)

        while url:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            yield from data.get("results", [])

            url = data.get("next")
            params = {}  # Next URL includes params

    def fetch_open_findings(
        self,
        severity_levels: list[str] | None = None,
    ) -> list[Finding]:
        """
        Fetch open findings from DefectDojo.

        Args:
            severity_levels: List of severity levels to filter (e.g., ["Critical", "High"])
                           Defaults to Critical and High if not specified.

        Returns:
            List of Finding objects matching the criteria.
        """
        if severity_levels is None:
            severity_levels = [Severity.CRITICAL.value, Severity.HIGH.value]

        params = {
            "active": "true",
            "duplicate": "false",
            "is_mitigated": "false",
        }

        if self.config.defectdojo_product_id:
            params["test__engagement__product"] = self.config.defectdojo_product_id

        findings = []
        for item in self._get_paginated("findings", params):
            severity = item.get("severity", "")
            if severity not in severity_levels:
                continue

            finding = Finding(
                id=item["id"],
                title=item.get("title", ""),
                severity=Severity(severity),
                component_name=item.get("component_name"),
                component_version=item.get("component_version"),
                file_path=item.get("file_path"),
                description=item.get("description", ""),
                mitigation=item.get("mitigation", ""),
                active=item.get("active", True),
                verified=item.get("verified", False),
                duplicate=item.get("duplicate", False),
            )
            findings.append(finding)

        logger.info(f"Fetched {len(findings)} open findings from DefectDojo")
        return findings

    def get_finding_by_id(self, finding_id: int) -> Finding | None:
        """Fetch a single finding by ID."""
        url = f"{self.base_url}/api/v2/findings/{finding_id}/"
        response = self.session.get(url)

        if response.status_code == 404:
            return None

        response.raise_for_status()
        item = response.json()

        return Finding(
            id=item["id"],
            title=item.get("title", ""),
            severity=Severity(item.get("severity", "Info")),
            component_name=item.get("component_name"),
            component_version=item.get("component_version"),
            file_path=item.get("file_path"),
            description=item.get("description", ""),
            mitigation=item.get("mitigation", ""),
            active=item.get("active", True),
            verified=item.get("verified", False),
            duplicate=item.get("duplicate", False),
        )

    def close_finding(self, finding_id: int, notes: str = "") -> bool:
        """Mark a finding as mitigated/closed."""
        url = f"{self.base_url}/api/v2/findings/{finding_id}/"
        payload = {
            "active": False,
            "is_mitigated": True,
        }
        if notes:
            payload["notes"] = [{"entry": notes}]

        response = self.session.patch(url, json=payload)
        return response.status_code == 200


def group_findings_by_image(findings: list[Finding]) -> dict[str, list[Finding]]:
    """
    Group findings by their associated container image.

    Returns:
        Dictionary mapping image:tag to list of findings.
    """
    grouped: dict[str, list[Finding]] = {}

    for finding in findings:
        image_tag = finding.image_tag
        if image_tag:
            grouped.setdefault(image_tag, []).append(finding)
        else:
            # Group by component name if no version
            key = finding.component_name or "unknown"
            grouped.setdefault(key, []).append(finding)

    return grouped
