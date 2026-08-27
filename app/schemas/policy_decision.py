from pydantic import BaseModel, Field


class PolicyDecision(BaseModel):
    approved: bool
    action: str
    expected_net_recovery: float
    reasons: list[str] = Field(default_factory=list)
