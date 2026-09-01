from fastapi import FastAPI

from app.api import recovery_events_router, payments_router, metrics_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name)
app.include_router(recovery_events_router)
app.include_router(payments_router)
app.include_router(metrics_router)

@app.get("/health", tags=["runtime"])
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "application": settings.app_name,
        "environment": settings.app_environment,
    }
