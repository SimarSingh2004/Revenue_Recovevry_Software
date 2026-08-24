from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class RecoveryEventCreate(BaseModel):
    event_id: str
    event_type: str
    occurred_at: datetime
    payment_id: str
    merchant_id: str
    customer_id: str
    amount: Decimal
    currency: str
    failure_code: Optional[str] = None
    failure_category: Optional[str] = None
    payment_method: str


class RecoveryEventResponse(RecoveryEventCreate):
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RecoveryCaseResponse(BaseModel):
    case_id: str
    event_id: str
    payment_id: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RecoveryEventIngestionResponse(BaseModel):
    status: str
    recovery_event: RecoveryEventResponse
    recovery_case: RecoveryCaseResponse


class ValidationErrorDetail(BaseModel):
    loc: list[str | int]
    msg: str
    type: str


class ValidationErrorResponse(BaseModel):
    detail: list[ValidationErrorDetail]
