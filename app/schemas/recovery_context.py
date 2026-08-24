from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class RecoveryCaseContext(BaseModel):
    case_id: str
    event_id: str
    payment_id: str
    status: str
    case_created_at: datetime


class CurrentPaymentFailureContext(BaseModel):
    customer_id: str
    amount: Decimal
    currency: str
    event_type: str
    event_occurred_at: datetime
    failure_code: str | None
    failure_category: str | None
    payment_method: str
    payment_attempt_number: int


class MerchantContextData(BaseModel):
    merchant_id: str
    recovery_enabled: bool
    allowed_recovery_actions: list[str]
    merchant_segment: str
    retry_cooldown_seconds: int
    max_recovery_attempts: int


class MerchantRecoveryHistoryItem(BaseModel):
    action: str
    outcome: str
    amount: Decimal
    intervention_cost: Decimal
    occurred_at: datetime


class MerchantRecoveryHistoryContext(BaseModel):
    history: list[MerchantRecoveryHistoryItem]
    recovery_attempt_count: int
    last_recovery_action: str | None
    last_recovery_outcome: str | None
    last_recovery_at: datetime | None


class HistoricalPayment(BaseModel):
    payment_id: str
    amount: Decimal
    currency: str
    payment_method: str
    status: str
    event_type: str
    occurred_at: datetime


class CustomerPaymentHistoryContext(BaseModel):
    historical_payments: list[HistoricalPayment]
    customer_payment_count: int
    customer_failed_payment_count: int
    customer_successful_payment_count: int
    customer_failure_rate: Decimal


class RecoveryContext(BaseModel):
    case: RecoveryCaseContext
    current_payment_failure: CurrentPaymentFailureContext
    merchant: MerchantContextData
    merchant_recovery_history: MerchantRecoveryHistoryContext
    customer_payment_history: CustomerPaymentHistoryContext
