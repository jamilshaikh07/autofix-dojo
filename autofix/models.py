"""Data models for the autofix service."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Severity(str, Enum):
    """Vulnerability severity levels."""

    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    INFO = "Info"


@dataclass
class Finding:
    """Represents a vulnerability finding from DefectDojo."""

    id: int
    title: str
    severity: Severity
    component_name: str | None = None
    component_version: str | None = None
    file_path: str | None = None
    description: str = ""
    mitigation: str = ""
    active: bool = True
    verified: bool = False
    duplicate: bool = False

    @property
    def image_tag(self) -> str | None:
        """Extract image:tag from component info if available."""
        if self.component_name and self.component_version:
            return f"{self.component_name}:{self.component_version}"
        return None


@dataclass
class FixSuggestion:
    """Represents a suggested fix for a vulnerability."""

    finding_id: int
    current_image: str
    current_tag: str
    suggested_tag: str
    confidence: str = "medium"  # low, medium, high
    reason: str = ""

    @property
    def full_current_image(self) -> str:
        return f"{self.current_image}:{self.current_tag}"

    @property
    def full_suggested_image(self) -> str:
        return f"{self.current_image}:{self.suggested_tag}"


@dataclass
class FixResult:
    """Result of applying a fix."""

    suggestion: FixSuggestion
    files_changed: list[str] = field(default_factory=list)
    branch_name: str = ""
    pr_url: str | None = None
    success: bool = False
    error: str = ""


@dataclass
class SLORecord:
    """Record for SLO tracking."""

    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    total_findings: int = 0
    auto_fixable: int = 0
    auto_fixed: int = 0
    prs_created: list[str] = field(default_factory=list)

    @property
    def slo_percentage(self) -> float:
        """Calculate SLO percentage."""
        if self.total_findings == 0:
            return 100.0
        return (self.auto_fixed / self.total_findings) * 100
