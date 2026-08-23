"""Application entry point and foundational HTTP routes."""

from fastapi import FastAPI

from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name)


@app.get("/health", tags=["runtime"])
def health_check() -> dict[str, str]:
    """Report whether the application process is available."""

    return {
        "status": "ok",
        "application": settings.app_name,
        "environment": settings.app_environment,
    }
