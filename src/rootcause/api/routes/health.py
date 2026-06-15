from datetime import UTC, datetime

from fastapi import APIRouter

from rootcause.api.schemas.health import HealthResponse
from rootcause.core.config import get_settings

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["system"])
async def health_check() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        version="0.1.0",
        timestamp=datetime.now(UTC),
        environment=settings.app_env,
    )
