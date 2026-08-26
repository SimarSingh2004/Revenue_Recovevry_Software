from sqlalchemy.orm import Session

from app.models import RecoveryCase
from app.schemas.llm_decision import LLMDecision
from app.services.llm_decision import LLMDecisionService
from app.services.recovery_context import load_recovery_context
from app.services.recovery_memory import (
    build_historical_insights,
    retrieve_recovery_memory,
)


def run_recovery_pipeline(
    db: Session,
    recovery_case: RecoveryCase,
    llm_decision_service: LLMDecisionService,
) -> LLMDecision:
    context = load_recovery_context(db, recovery_case.case_id)
    historical_insights = build_historical_insights(
        retrieve_recovery_memory(db, context)
    )
    return llm_decision_service.decide(context, historical_insights)
