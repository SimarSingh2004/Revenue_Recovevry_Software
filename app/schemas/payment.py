from decimal import Decimal

from pydantic import BaseModel

from app.simulator.payments import PaymentOutcome


class PaymentCreate(BaseModel):
    payment_id: str
    merchant_id: str
    customer_id: str
    amount: Decimal
    currency: str
    payment_method: str
    simulation_outcome: PaymentOutcome