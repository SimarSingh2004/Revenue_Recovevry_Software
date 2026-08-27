from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session 

from app.models import RecoveryLearningMemory
from app.schemas.recovery_context import RecoveryContext
from app.schemas.recovery_memory import HistoricalRecoveryInsight


def store_recovery_memory(
    db: Session,
    *,
    failure_code: str | None,
    failure_category: str | None,
    payment_method: str,
    payment_attempt_number: int,
    action: str,
    outcome: str,
    llm_p_pred: Decimal,
    gt_p: Decimal,
    baseline_p: Decimal,
    net_recovery_value: Decimal,
    financial_impact: str,
) -> RecoveryLearningMemory:
    memory = RecoveryLearningMemory(
        failure_code=failure_code,
        failure_category=failure_category,
        payment_method=payment_method,
        payment_attempt_number=payment_attempt_number,
        action=action,
        outcome=outcome,
        llm_p_pred=llm_p_pred,
        gt_p=gt_p,
        baseline_p=baseline_p,
        net_recovery_value=net_recovery_value,
        financial_impact=financial_impact,
    )
    db.add(memory)
    db.commit()
    db.refresh(memory)
    return memory


def retrieve_recovery_memory(
    db: Session,
    context: RecoveryContext,
) -> list[RecoveryLearningMemory]:
    current = context.current_payment_failure
    records = list(
        db.scalars(
            select(RecoveryLearningMemory).order_by(
                RecoveryLearningMemory.created_at.desc(),
                RecoveryLearningMemory.id.desc(),
            )
        )
    )

    exact_matches = [
        record
        for record in records
        if record.failure_code == current.failure_code
        and record.payment_method == current.payment_method
    ]
    nearby_attempt_matches = [
        record
        for record in records
        if record.failure_code == current.failure_code
        and record.payment_method == current.payment_method
    ]
    category_matches = [
        record
        for record in records
        if record.failure_category == current.failure_category
    ]

    selected: list[RecoveryLearningMemory] = []
    selected_ids: set[int] = set()
    selected_actions: set[str] = set()

    for matches in (exact_matches, nearby_attempt_matches, category_matches):
        if len(selected) == 3:
            break
        _select_diverse_records(
            matches,
            selected,
            selected_ids,
            selected_actions,
        )

    return selected


def build_historical_insights(
    records: list[RecoveryLearningMemory],
) -> list[HistoricalRecoveryInsight]:
    return [
        HistoricalRecoveryInsight(
            failure_code=record.failure_code,
            failure_category=record.failure_category,
            payment_method=record.payment_method,
            action=record.action,
            outcome=record.outcome,
            financial_impact=record.financial_impact,
        )
        for record in records
    ]


def _select_diverse_records(
    candidates: list[RecoveryLearningMemory],
    selected: list[RecoveryLearningMemory],
    selected_ids: set[int],
    selected_actions: set[str],
) -> None:
    success_candidates = [
        record for record in candidates if record.outcome.upper() == "SUCCESS"
    ]
    failed_candidates = [
        record for record in candidates if record.outcome.upper() == "FAILED"
    ]
    other_candidates = [
        record
        for record in candidates
        if record.outcome.upper() not in {"SUCCESS", "FAILED"}
    ]

    if not any(record.outcome.upper() == "SUCCESS" for record in selected):
        _add_records(success_candidates, selected, selected_ids, selected_actions)

    failed_count = sum(record.outcome.upper() == "FAILED" for record in selected)
    if failed_count < 2:
        _add_records(failed_candidates, selected, selected_ids, selected_actions)

    _add_records(success_candidates, selected, selected_ids, selected_actions)
    _add_records(failed_candidates, selected, selected_ids, selected_actions)
    _add_records(other_candidates, selected, selected_ids, selected_actions)


def _add_records(
    candidates: list[RecoveryLearningMemory],
    selected: list[RecoveryLearningMemory],
    selected_ids: set[int],
    selected_actions: set[str],
) -> None:
    for record in candidates:
        if len(selected) == 3:
            return
        if record.id in selected_ids or record.action in selected_actions:
            continue
        selected.append(record)
        selected_ids.add(record.id)
        selected_actions.add(record.action)
