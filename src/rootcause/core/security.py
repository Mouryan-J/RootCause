from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from rootcause.core.config import get_settings

_bearer = HTTPBearer(auto_error=False)


async def require_api_key(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> None:
    """FastAPI dependency that validates Bearer token against API_SECRET_KEY.

    Auth is disabled entirely when API_SECRET_KEY is empty (development default).
    """
    settings = get_settings()
    if not settings.api_secret_key:
        return  # auth disabled in dev
    if credentials is None or credentials.credentials != settings.api_secret_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
