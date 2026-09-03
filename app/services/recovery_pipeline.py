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
    record_recovery_memory,
    retrieve_recovery_memory,
)
from app.simulator.payment_provider import (
    PaymentProviderSimulator,
    SimulationOutcome,
    SimulationResult
)
from app.simulator.ground_truth import ground_truth_probability
from app.core.recovery_actions import get_action_cost
import logging

logger=logging.getLogger(__name__)


def run_recovery_pipeline(
    db: Session,
    recovery_case: RecoveryCase,
    llm_decision_service: LLMDecisionService,
    policy_engine: PolicyEngine | None = None,
    payment_provider: PaymentProviderSimulator | None = None,
    decision_capture:dict |None = None
) -> tuple[PolicyDecision, SimulationResult | None]:
    context = load_recovery_context(db, recovery_case.case_id)
    now=datetime.now(timezone.utc)
    historical_insights = build_historical_insights(
        retrieve_recovery_memory(db, context)
    )
    logger.info(
        "[RecoveryPipeline] Historical insights supplied to LLM: %d",
        len(historical_insights),
    )

    engine = policy_engine or PolicyEngine()

    policy_feedback=[]
    rejected_actions=set()
    max_policy_retries=2

    for _ in range(max_policy_retries+1):
        try:
            decision: LLMDecision = llm_decision_service.decide(
                context, historical_insights, policy_feedback=policy_feedback
            )
            if decision_capture is not None:
                decision_capture["rationale"] = decision.rationale
        except RuntimeError:
            db.rollback()
            raise 
        if decision.action in rejected_actions:
            policy_feedback.append({
                "action": decision.action,
                "reasons": ["Action previously rejected by policy layer."],
            })

        expected_net_recovery = expected_net_recovery_value(
            context,
            decision.action,
            decision.predicted_p_recovery,
        )
   
        policy_decision=engine.evaluate(context, decision.action, expected_net_recovery, now=now)

        if policy_decision.approved:
            break

        rejected_actions.add(decision.action)

        policy_feedback.append({
            "action": decision.action,
            "reasons": policy_decision.reasons,
        })
    else:
        return policy_decision, None


    if not policy_decision.approved:
        return policy_decision, None

    if payment_provider is None:
        raise ValueError("PaymentProviderSimulator is required when policy approves an action.")

    success_probability = ground_truth_probability(context,policy_decision.action,now=now)

    simulation_result=payment_provider.execute(
        policy_decision.action,
        context,
        success_probability=success_probability,
    )

    record_recovery_memory(
        db,
        context=context,
        decision=decision,
        simulation_result=simulation_result,
        gt_p=success_probability,
        now=now
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

def run_recovery_until_resolved(
        db:Session,
        recovery_case:RecoveryCase,
        llm_decision_service:LLMDecisionService,
        policy_engine:PolicyEngine | None = None,
        payment_provider:PaymentProviderSimulator | None = None,
        decision_capture:dict |None = None
)-> tuple[PolicyDecision, SimulationResult | None]:
    while True:
        policy_decision, simulation_result = run_recovery_pipeline(
            db,
            recovery_case,
            llm_decision_service,
            policy_engine=policy_engine,
            payment_provider=payment_provider,
            decision_capture=decision_capture
        )

        if simulation_result is None:
            return policy_decision, None

        if simulation_result.outcome == SimulationOutcome.SUCCESS:
            recovery_case.status = "RECOVERED"
            db.commit()
            return policy_decision, simulation_result

        if not simulation_result.is_provider_execution:
            recovery_case.status = (
                "STOPPED"
                if simulation_result.action.value == "STOP"
                else "ESCALATED"
            )
            db.commit()
            return policy_decision, simulation_result
