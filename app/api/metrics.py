from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db_session
from app.services.recovery_metrics import get_recovery_metrics

router=APIRouter(prefix="/metrics", tags=["metrics"])

@router.get("/recovery")
def recovery_metrics(
    db:Session=Depends(get_db_session)
):
    return get_recovery_metrics(db)