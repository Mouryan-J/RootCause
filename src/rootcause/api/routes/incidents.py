import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select

from rootcause.agents.graph import run_analysis
from rootcause.api.schemas.incident import (
    AnalysisResult,
    AnalysisStatus,
    IncidentListItem,
    IncidentRequest,
    IncidentResponse,
    RootCause,
)
from rootcause.core.logging import get_logger
from rootcause.core.security import require_api_key
from rootcause.db.models import Incident
from rootcause.db.postgres import get_session
from rootcause.db.redis_client import get_redis

router = APIRouter(prefix="/incidents", tags=["incidents"])
logger = get_logger(__name__)

_CACHE_TTL = 1800  # 30 minutes for completed/failed results


def _incident_to_result(incident: Incident) -> AnalysisResult:
    root_causes = [
        RootCause(
            description=rc["description"],
            confidence=rc["confidence"],
            evidence=rc.get("evidence") or [],
        )
        for rc in (incident.root_causes or [])
    ]
    return AnalysisResult(
        incident_id=incident.id,
        status=AnalysisStatus(incident.status),
        created_at=incident.created_at,
        completed_at=incident.completed_at,
        root_causes=root_causes,
        contributing_factors=incident.contributing_factors or [],
        remediation_steps=incident.remediation_steps or [],
        summary=incident.summary,
        runbooks_referenced=incident.runbooks_referenced or [],
        model_used=incident.model_used,
    )


async def _run_and_store(incident_id: uuid.UUID, request: IncidentRequest) -> None:
    async with get_session() as session:
        incident = await session.get(Incident, incident_id)
        if incident:
            incident.status = AnalysisStatus.processing

    try:
        final = await run_analysis(
            incident_id=incident_id,
            title=request.title,
            description=request.description,
            service=request.service,
            severity=request.severity.value,
            logs=request.logs,
            metrics=request.metrics,
        )
        async with get_session() as session:
            incident = await session.get(Incident, incident_id)
            if incident:
                incident.status = AnalysisStatus.complete
                incident.completed_at = datetime.now(UTC)
                incident.root_causes = final.get("root_causes") or []
                incident.contributing_factors = final.get("contributing_factors") or []
                incident.remediation_steps = final.get("remediation_steps") or []
                incident.summary = final.get("summary") or ""
                incident.runbooks_referenced = final.get("runbooks_referenced") or []
                incident.model_used = final.get("model_used") or ""

        logger.info("analysis_stored", incident_id=str(incident_id))

        # Cache the completed result
        redis = get_redis()
        if redis:
            async with get_session() as session:
                incident = await session.get(Incident, incident_id)
                if incident:
                    result = _incident_to_result(incident)
                    await redis.setex(
                        f"incident:{incident_id}", _CACHE_TTL, result.model_dump_json()
                    )

    except Exception as exc:
        logger.error("analysis_failed", incident_id=str(incident_id), error=str(exc))
        async with get_session() as session:
            incident = await session.get(Incident, incident_id)
            if incident:
                incident.status = AnalysisStatus.failed
                incident.completed_at = datetime.now(UTC)


@router.get("/", response_model=list[IncidentListItem], dependencies=[Depends(require_api_key)])
async def list_incidents(limit: int = Query(default=20, ge=1, le=100)) -> list[IncidentListItem]:
    async with get_session() as session:
        stmt = select(Incident).order_by(Incident.created_at.desc()).limit(limit)
        rows = (await session.execute(stmt)).scalars().all()
    return [
        IncidentListItem(
            incident_id=row.id,
            title=row.title,
            service=row.service,
            severity=row.severity,
            status=AnalysisStatus(row.status),
            created_at=row.created_at,
            completed_at=row.completed_at,
        )
        for row in rows
    ]


@router.post("/analyze", response_model=IncidentResponse, status_code=202, dependencies=[Depends(require_api_key)])
async def analyze_incident(
    request: IncidentRequest, background_tasks: BackgroundTasks
) -> IncidentResponse:
    incident_id = uuid.uuid4()
    now = datetime.now(UTC)

    async with get_session() as session:
        incident = Incident(
            id=incident_id,
            title=request.title,
            description=request.description,
            service=request.service,
            severity=request.severity.value,
            started_at=request.started_at,
            resolved_at=request.resolved_at,
            logs=request.logs,
            metrics=request.metrics,
            labels=request.labels,
            status=AnalysisStatus.queued,
            created_at=now,
        )
        session.add(incident)

    background_tasks.add_task(_run_and_store, incident_id, request)

    logger.info(
        "incident_queued",
        incident_id=str(incident_id),
        service=request.service,
        severity=request.severity,
    )
    return IncidentResponse(
        incident_id=incident_id,
        status=AnalysisStatus.queued,
        created_at=now,
        message="Incident queued for analysis. Poll GET /incidents/{incident_id} for results.",
    )


@router.get("/{incident_id}", response_model=AnalysisResult, dependencies=[Depends(require_api_key)])
async def get_incident(incident_id: uuid.UUID) -> AnalysisResult:
    # Try Redis cache first for completed/failed results
    redis = get_redis()
    if redis:
        cached = await redis.get(f"incident:{incident_id}")
        if cached:
            return AnalysisResult.model_validate_json(cached)

    async with get_session() as session:
        incident = await session.get(Incident, incident_id)

    if incident is None:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")

    result = _incident_to_result(incident)

    # Cache once terminal
    if redis and incident.status in (AnalysisStatus.complete, AnalysisStatus.failed):
        await redis.setex(f"incident:{incident_id}", _CACHE_TTL, result.model_dump_json())

    return result
