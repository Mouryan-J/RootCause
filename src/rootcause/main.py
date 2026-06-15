import uvicorn

from rootcause.api.app import create_app
from rootcause.core.config import get_settings

app = create_app()

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "rootcause.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.app_env == "development",
        log_config=None,
    )
