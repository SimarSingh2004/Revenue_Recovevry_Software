from pydantic import BaseModel, ConfigDict, Field


class LLMDecision(BaseModel):
    action: str
    predicted_p_recovery: float = Field(
        ge=0.0,
        le=1.0,
        description="Predicted probability of recovery",
    )
    rationale: str

    model_config = ConfigDict(extra="forbid")


