from pydantic import BaseModel


class HistoricalRecoveryInsight(BaseModel):
    failure_code: str | None
    failure_category: str | None
    payment_method: str
    payment_attempt_number: int
    action: str
    outcome: str
    financial_impact: str
