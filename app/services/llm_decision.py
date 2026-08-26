import json

from google import genai
from google.genai import types

from app.core.config import Settings, get_settings
from app.schemas.llm_decision import LLMDecision
from app.schemas.recovery_context import RecoveryContext
from app.schemas.recovery_memory import HistoricalRecoveryInsight

SYSTEM_PROMPT = """
You are a payment recovery decision-maker.

Your task is to analyze the provided RecoveryContext and select the single most appropriate recovery action for the current payment failure.

You MUST select exactly one action from the provided allowed recovery actions. Do not invent, modify, or select any action outside that list. If all active recovery paths are unviable or exhausted, choose STOP or ESCALATE, if present in the allowed list.

Base your decision ONLY on the current RecoveryContext, the provided allowed recovery actions, and any historical cases provided. Do not use or assume any information that is not provided.

Historical cases, when provided, are evidence only. Use them to inform your reasoning, but do not copy their actions blindly; independently evaluate the current RecoveryContext.

Consider the failure code, error category, payment method, attempt number, merchant settings, customer history, and prior recovery attempts when making your decision.

Provide:

1. The chosen action from the allowed list.
2. An estimated realistic recovery probability (P ∈ [0.0, 1.0]) representing the likelihood that the selected action will successfully recover the payment, given the RecoveryContext.
3. A concise technical rationale explaining why this action was chosen over the available alternatives.
"""

class LLMDecisionService:
    def __init__(self,client:genai.Client,model:str):
        self._client=client
        self._model=model

    def decide(
        self,
        context: RecoveryContext,
        historical_insights: list[HistoricalRecoveryInsight] | None = None,
    ) -> LLMDecision:
        allowed_actions=list(context.merchant.allowed_recovery_actions)
        if not allowed_actions:
            raise ValueError("No allowed recovery actions provided in the context.")

        payload={
            "recovery_context":context.model_dump(mode="json"),
            "allowed_recovery_actions":allowed_actions,
            "historical_insights": [
                insight.model_dump(mode="json")
                for insight in historical_insights or []
            ],
        }

        response=self._client.models.generate_content(
            model=self._model,
            contents=json.dumps(payload,indent=2),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.0,
                response_mime_type="application/json",
                response_schema=LLMDecision
            )
        )

        decision=LLMDecision.model_validate_json(response.text)

        if decision.action not in allowed_actions:
            raise ValueError(f"LLM returned an action '{decision.action}' that is not in the allowed recovery actions")

        return decision

def get_llm_decision_service(settings:Settings | None = None)->LLMDecisionService:
    resolved_settings=settings or get_settings()
    return LLMDecisionService(client=genai.Client(api_key=resolved_settings.gemini_api_key),model=resolved_settings.gemini_model)
