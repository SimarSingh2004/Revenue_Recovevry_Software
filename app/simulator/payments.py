from dataclasses import dataclass
from enum import Enum
from random import Random

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

   