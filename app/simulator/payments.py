from dataclasses import dataclass
from enum import Enum
import random

class PaymentOutcome(str,Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"

@dataclass
class PaymentSimulationResult:
    payment_id:str
    outcome:PaymentOutcome

class PaymentSimulator:

    def process(
        self,
        payment_id: str,
        *,
        outcome: PaymentOutcome,
    ) -> PaymentSimulationResult:
        return PaymentSimulationResult(
            payment_id=payment_id,
            outcome=outcome,
        )

class FailureCategory(str,Enum):
        TEMPORARY_FAILURE: str = "TEMPORARY_FAILURE"
        INSUFFICIENT_FUNDS: str = "INSUFFICIENT_FUNDS"
        NETWORK_ERROR: str = "NETWORK_ERROR"
        PROCESSING_ERROR: str = "PROCESSING_ERROR"
        EXPIRED_CARD: str = "EXPIRED_CARD"
        INVALID_CARD: str = "INVALID_CARD"
        FRAUD: str = "FRAUD"
        UNKNOWN: str = "UNKNOWN"

def get_failure_category(payment_method: str) -> "FailureCategory":
            if payment_method!="CARD":
                eligible=[
                        c for c in FailureCategory
                         if c not in (FailureCategory.EXPIRED_CARD, FailureCategory.INVALID_CARD) 
                        ]
                return random.choice(eligible)
            return random.choice(list(FailureCategory))

   