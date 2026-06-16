import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Request fields
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(String)
    service: Mapped[str] = mapped_column(String(200))
    severity: Mapped[str] = mapped_column(String(50))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    logs: Mapped[str | None] = mapped_column(String, nullable=True)
    metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    labels: Mapped[dict] = mapped_column(JSON, default=dict)

    # Lifecycle
    status: Mapped[str] = mapped_column(String(50), default="queued")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Analysis output
    root_causes: Mapped[list] = mapped_column(JSON, default=list)
    contributing_factors: Mapped[list] = mapped_column(JSON, default=list)
    remediation_steps: Mapped[list] = mapped_column(JSON, default=list)
    summary: Mapped[str | None] = mapped_column(String, nullable=True)
    runbooks_referenced: Mapped[list] = mapped_column(JSON, default=list)
    model_used: Mapped[str | None] = mapped_column(String, nullable=True)
