from dataclasses import dataclass
from enum import Enum
from random import Random

from app.core.recovery_actions import RecoveryAction
from app.schemas.recovery_context import RecoveryContext


class SimulationOutcome(str, Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    NOT_EXECUTED = "NOT_EXECUTED"


@dataclass(frozen=True)
class SimulationResult:
    action: RecoveryAction
    outcome: SimulationOutcome
    is_payment_attempt: bool
    is_provider_execution: bool
    provider_reference: str | None


class PaymentProviderSimulator:

    def __init__(self, random_source: Random | None = None):
        self._random = random_source or Random()
        self._reference_number = 0

    def execute(
        self,
        action: RecoveryAction | str,
        context: RecoveryContext,
        *,
        success_probability: float,
    ) -> SimulationResult:
        resolved_action = RecoveryAction(action)
        self._validate_probability(success_probability)

        if resolved_action in (RecoveryAction.ESCALATE, RecoveryAction.STOP):
            return SimulationResult(
                action=resolved_action,
                outcome=SimulationOutcome.NOT_EXECUTED,
                is_payment_attempt=False,
                is_provider_execution=False,
                provider_reference=None,
            )

        is_provider_execution = resolved_action in {
            RecoveryAction.RETRY_PAYMENT,
            RecoveryAction.ALTERNATE_PAYMENT_METHOD,
            RecoveryAction.SEND_PAYMENT_LINK,
        }
        is_payment_attempt = resolved_action in {
            RecoveryAction.RETRY_PAYMENT,
            RecoveryAction.ALTERNATE_PAYMENT_METHOD,
            RecoveryAction.SEND_PAYMENT_LINK,
        }
        outcome = (
            SimulationOutcome.SUCCESS
            if self._random.random() < success_probability
            else SimulationOutcome.FAILURE
        )

        return SimulationResult(
            action=resolved_action,
            outcome=outcome,
            is_payment_attempt=is_payment_attempt,
            is_provider_execution=is_provider_execution,
            provider_reference=self._next_reference(context, resolved_action)
            if is_provider_execution
            else None,
        )

    @staticmethod
    def _validate_probability(success_probability: float) -> None:
        if not 0 <= success_probability <= 1:
            raise ValueError("success_probability must be between 0 and 1")

    def _next_reference(self, context: RecoveryContext, action: RecoveryAction) -> str:
        self._reference_number += 1
        return f"sim_{action.value.lower()}_{context.case.payment_id}_{self._reference_number}"
