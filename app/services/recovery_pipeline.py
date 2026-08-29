from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import RecoveryCase, MerchantHistory 
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
from app.simulator.payment_provider import (
    PaymentProviderSimulator,
    SimulationResult
)
from app.core.recovery_actions import get_action_cost


def run_recovery_pipeline(
    db: Session,
    recovery_case: RecoveryCase,
    llm_decision_service: LLMDecisionService,
    policy_engine: PolicyEngine | None = None,
    payment_provider: PaymentProviderSimulator | None = None,
    success_probability: float | None = None,
) -> tuple[PolicyDecision, SimulationResult | None]:
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
    policy_decision=engine.evaluate(context, decision.action, expected_net_recovery, now=now)

    if not policy_decision.approved:
        return policy_decision, None

    if payment_provider is None:
        raise ValueError("PaymentProviderSimulator is required when policy approves an action.")

    if success_probability is None:
        raise ValueError("success_probability is required when policy approves an action.")

    simulation_result=payment_provider.execute(
        policy_decision.action,
        context,
        success_probability=success_probability,
    )

    db.add(
        MerchantHistory(
            merchant_id=context.merchant.merchant_id,
            case_id=context.case.case_id,
            action=simulation_result.action.value,
            outcome=simulation_result.outcome.value,
            amount=context.current_payment_failure.amount,
            intervention_cost=get_action_cost(simulation_result.action),
            occurred_at=now
        )
    )

    db.commit()

    return policy_decision, simulation_result
