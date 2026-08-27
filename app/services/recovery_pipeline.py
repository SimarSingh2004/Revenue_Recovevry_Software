from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import RecoveryCase
from app.schemas.llm_decision import LLMDecision
from app.schemas.policy_decision import PolicyDecision
from app.services.llm_decision import LLMDecisionService
from app.services.optimizer import expected_net_recovery_value
from app.services.policy_engine import PolicyEngine
from app.services.recovery_context import load_recovery_context
from app.services.recovery_memory import (
    build_historical_insights,
    retrieve_recovery_memory,
)


def run_recovery_pipeline(
    db: Session,
    recovery_case: RecoveryCase,
    llm_decision_service: LLMDecisionService,
    policy_engine: PolicyEngine | None = None,
) -> PolicyDecision:
    context = load_recovery_context(db, recovery_case.case_id)
    now=datetime.now(timezone.utc)
    historical_insights = build_historical_insights(
        retrieve_recovery_memory(db, context)
    )
    decision: LLMDecision = llm_decision_service.decide(context, historical_insights)
    expected_net_recovery = expected_net_recovery_value(
        context,
        decision.action,
        decision.predicted_p_recovery,
    )
    engine = policy_engine or PolicyEngine()
    return engine.evaluate(context, decision.action, expected_net_recovery, now=now)
