from sqlalchemy.orm import Session

from app.models import RecoveryCase
from app.schemas.llm_decision import LLMDecision
from app.services.llm_decision import LLMDecisionService
from app.services.recovery_context import load_recovery_context


def run_recovery_pipeline(
    db: Session,
    recovery_case: RecoveryCase,
    llm_decision_service: LLMDecisionService,
) -> LLMDecision:
    context = load_recovery_context(db, recovery_case.case_id)
    return llm_decision_service.decide(context)
