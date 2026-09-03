from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.recovery import RecoveryLearningMemory


def get_recovery_metrics(db: Session) -> dict:
    total_attempts = (
        db.query(func.count(RecoveryLearningMemory.id))
        .filter(RecoveryLearningMemory.outcome != "STOPPED")
        .filter(RecoveryLearningMemory.outcome != "ESCALATED")
        .scalar()
        or 0
    )

    successful_recoveries = (
        db.query(func.count(RecoveryLearningMemory.id))
        .filter(RecoveryLearningMemory.financial_impact == "POSITIVE_RECOVERY")
        .scalar()
        or 0
    )

    total_recovered_value = (
        db.query(func.sum(RecoveryLearningMemory.net_recovery_value))
        .filter(RecoveryLearningMemory.financial_impact == "POSITIVE_RECOVERY")
        .scalar()
        or 0
    )

    total_fee_loss = (
        db.query(func.sum(RecoveryLearningMemory.net_recovery_value))
        .filter(RecoveryLearningMemory.financial_impact == "FEE_LOSS")
        .scalar()
        or 0
    )

    net_recovered_value = (
        db.query(func.sum(RecoveryLearningMemory.net_recovery_value))
        .scalar()
        or 0
    )

    success_rate = (
        successful_recoveries / total_attempts
        if total_attempts
        else 0
    )

    calibration_rows=(
        db.query(
            RecoveryLearningMemory.llm_p_pred,
            RecoveryLearningMemory.gt_p,
            RecoveryLearningMemory.baseline_p,
        ).filter(
            RecoveryLearningMemory.financial_impact.in_(["POSITIVE_RECOVERY", "FEE_LOSS"])
        ).all()
    )

    if calibration_rows:
        llm_error=sum(abs(float(row.llm_p_pred) - float(row.gt_p)) for row in calibration_rows) / len(calibration_rows)
        baseline_error=sum(abs(float(row.baseline_p) - float(row.gt_p)) for row in calibration_rows) / len(calibration_rows)
    else:
        llm_error=None
        baseline_error=None

    return {
        "total_recovery_attempts": total_attempts,
        "successful_recoveries": successful_recoveries,
        "recovery_success_rate": round(success_rate, 4),
        "total_recovered_value": round(float(total_recovered_value), 2),
        "total_fee_loss": round(float(abs(total_fee_loss)), 2),
        "net_recovered_value": round(float(net_recovered_value), 2),
        "llm_error": round(llm_error, 4) if llm_error is not None else None,
        "baseline_error": round(baseline_error, 4) if baseline_error is not None else None,
    }