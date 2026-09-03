from fastapi import FastAPI

from app.api import recovery_events_router, payments_router, metrics_router
from app.core.config import get_settings
from fastapi.middleware.cors import CORSMiddleware

settings = get_settings()

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    )
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
