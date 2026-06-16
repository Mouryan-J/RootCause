from fastapi import APIRouter, Depends

from rootcause.core.security import require_api_key
from rootcause.db.neo4j_client import get_service_dependencies

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/{service_name}", dependencies=[Depends(require_api_key)])
async def get_graph(service_name: str) -> dict:
    return get_service_dependencies(service_name)
