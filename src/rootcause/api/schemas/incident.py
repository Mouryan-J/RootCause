import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Severity(StrEnum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class AnalysisStatus(StrEnum):
    queued = "queued"
    processing = "processing"
    complete = "complete"
    failed = "failed"


class IncidentRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str = Field(..., min_length=1)
    service: str = Field(..., min_length=1, max_length=200)
    severity: Severity
    started_at: datetime
    resolved_at: datetime | None = None
    logs: str | None = Field(default=None, description="Raw log snippet relevant to the incident")
    metrics: dict[str, Any] | None = Field(default=None, description="Key metric values at incident time")
    labels: dict[str, str] = Field(default_factory=dict)


class IncidentResponse(BaseModel):
    incident_id: uuid.UUID
    status: AnalysisStatus
    created_at: datetime
    message: str


class RootCause(BaseModel):
    description: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence: list[str]


class AnalysisResult(BaseModel):
    incident_id: uuid.UUID
    status: AnalysisStatus
    created_at: datetime
    completed_at: datetime | None = None
    root_causes: list[RootCause] = []
    contributing_factors: list[str] = []
    remediation_steps: list[str] = []
    summary: str | None = None
    runbooks_referenced: list[str] = []
    model_used: str | None = None


class IncidentListItem(BaseModel):
    incident_id: uuid.UUID
    title: str
    service: str
    severity: Severity
    status: AnalysisStatus
    created_at: datetime
    completed_at: datetime | None = None
