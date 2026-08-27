import unittest
import json
from unittest.mock import MagicMock

from pydantic import ValidationError

from app.schemas.llm_decision import LLMDecision
from app.schemas.recovery_context import (
    RecoveryCaseContext,
    CurrentPaymentFailureContext,
    MerchantContextData,
    MerchantRecoveryHistoryItem,
    MerchantRecoveryHistoryContext,
    HistoricalPayment,
    CustomerPaymentHistoryContext,
    RecoveryContext,
)
from app.schemas.recovery_memory import HistoricalRecoveryInsight
from app.services.llm_decision import LLMDecisionService


class TestLLMDecisionService(unittest.TestCase):

    def setUp(self):
        self.client = MagicMock()
        self.service = LLMDecisionService(
            client=self.client,
            model="gemini-test-model",
        )

        self.context = RecoveryContext(
            case=RecoveryCaseContext(
                case_id="case_001",
                event_id="event_001",
                payment_id="payment_001",
                status="OPEN",
                case_created_at="2026-08-26T10:00:00Z",
            ),
            current_payment_failure=CurrentPaymentFailureContext(
                customer_id="customer_001",
                amount="100.00",
                currency="INR",
                event_type="PAYMENT_FAILED",
                event_occurred_at="2026-08-26T10:00:00Z",
                failure_code="INSUFFICIENT_FUNDS",
                failure_category="HARD_DECLINE",
                payment_method="CARD",
                payment_attempt_number=1,
            ),
            merchant=MerchantContextData(
                merchant_id="merchant_001",
                recovery_enabled=True,
                allowed_recovery_actions=[
                    "RETRY_PAYMENT",
                    "ALTERNATE_PAYMENT_METHOD",
                    "SEND_PAYMENT_LINK",
                    "ESCALATE",
                    "STOP",
                ],
                merchant_segment="SMB",
                retry_cooldown_seconds=3600,
                max_recovery_attempts=3,
            ),
            merchant_recovery_history=MerchantRecoveryHistoryContext(
                history=[
                    MerchantRecoveryHistoryItem(
                        action="RETRY_PAYMENT",
                        outcome="FAILED",
                        amount="100.00",
                        intervention_cost="1.00",
                        occurred_at="2026-08-26T09:00:00Z",
                    )
                ],
                recovery_attempt_count=1,
                last_recovery_action="RETRY_PAYMENT",
                last_recovery_outcome="FAILED",
                last_recovery_at="2026-08-26T09:00:00Z",
            ),
            customer_payment_history=CustomerPaymentHistoryContext(
                historical_payments=[
                    HistoricalPayment(
                        payment_id="payment_previous_001",
                        amount="80.00",
                        currency="INR",
                        payment_method="CARD",
                        status="SUCCESS",
                        event_type="PAYMENT_CAPTURED",
                        occurred_at="2026-08-20T10:00:00Z",
                    )
                ],
                customer_payment_count=1,
                customer_failed_payment_count=0,
                customer_successful_payment_count=1,
                customer_failure_rate="0.00",
            ),
        )

    def _mock_gemini_response(
        self,
        action: str,
        predicted_p_recovery: float,
        rationale: str,
    ):
        response = MagicMock()

        response.text = LLMDecision(
            action=action,
            predicted_p_recovery=predicted_p_recovery,
            rationale=rationale,
        ).model_dump_json()

        return response

    def test_valid_llm_decision_is_returned(self):
        response = self._mock_gemini_response(
            action="RETRY_PAYMENT",
            predicted_p_recovery=0.72,
            rationale=(
                "The failure is recoverable and the customer has "
                "previously completed successful payments."
            ),
        )

        self.client.models.generate_content.return_value = response

        decision = self.service.decide(self.context)

        self.assertEqual(decision.action, "RETRY_PAYMENT")
        self.assertEqual(decision.predicted_p_recovery, 0.72)
        self.assertEqual(
            decision.rationale,
            (
                "The failure is recoverable and the customer has "
                "previously completed successful payments."
            ),
        )

    def test_gemini_is_called_once(self):
        response = self._mock_gemini_response(
            action="RETRY_PAYMENT",
            predicted_p_recovery=0.72,
            rationale="Retry is appropriate.",
        )

        self.client.models.generate_content.return_value = response

        self.service.decide(self.context)

        self.client.models.generate_content.assert_called_once()

    def test_correct_model_is_used(self):
        response = self._mock_gemini_response(
            action="RETRY_PAYMENT",
            predicted_p_recovery=0.72,
            rationale="Retry is appropriate.",
        )

        self.client.models.generate_content.return_value = response

        self.service.decide(self.context)

        call_kwargs = self.client.models.generate_content.call_args.kwargs

        self.assertEqual(
            call_kwargs["model"],
            "gemini-test-model",
        )

    def test_allowed_actions_are_sent_to_gemini(self):
        response = self._mock_gemini_response(
            action="RETRY_PAYMENT",
            predicted_p_recovery=0.72,
            rationale="Retry is appropriate.",
        )

        self.client.models.generate_content.return_value = response

        self.service.decide(self.context)

        call_kwargs = self.client.models.generate_content.call_args.kwargs
        contents = call_kwargs["contents"]

        self.assertIn("allowed_recovery_actions", contents)

        for action in self.context.merchant.allowed_recovery_actions:
            self.assertIn(action, contents)

    def test_recovery_context_is_sent_to_gemini(self):
        response = self._mock_gemini_response(
            action="RETRY_PAYMENT",
            predicted_p_recovery=0.72,
            rationale="Retry is appropriate.",
        )

        self.client.models.generate_content.return_value = response

        self.service.decide(self.context)

        call_kwargs = self.client.models.generate_content.call_args.kwargs
        contents = call_kwargs["contents"]

        self.assertIn("recovery_context", contents)
        self.assertIn(self.context.case.case_id, contents)
        self.assertIn(
            self.context.current_payment_failure.failure_code,
            contents,
        )
        self.assertIn(
            self.context.current_payment_failure.payment_method,
            contents,
        )

    def test_historical_insights_include_only_safe_fields(self):
        response = self._mock_gemini_response(
            action="RETRY_PAYMENT",
            predicted_p_recovery=0.72,
            rationale="Retry is appropriate.",
        )
        self.client.models.generate_content.return_value = response
        insight = HistoricalRecoveryInsight(
            failure_code="INSUFFICIENT_FUNDS",
            failure_category="HARD_DECLINE",
            payment_method="CARD",
            payment_attempt_number=1,
            action="SEND_PAYMENT_LINK",
            outcome="FAILED",
            financial_impact="FEE_LOSS",
        )

        decision = self.service.decide(self.context, [insight])

        payload = json.loads(
            self.client.models.generate_content.call_args.kwargs["contents"]
        )
        self.assertEqual(decision.action, "RETRY_PAYMENT")
        self.assertEqual(
            payload["historical_insights"],
            [insight.model_dump(mode="json")],
        )
        self.assertNotIn("gt_p", payload["historical_insights"][0])
        self.assertNotIn("baseline_p", payload["historical_insights"][0])
        self.assertNotIn("net_recovery_value", payload["historical_insights"][0])

    def test_unallowed_action_is_rejected(self):
        restricted_context = self.context.model_copy(
            deep=True,
            update={
                "merchant": self.context.merchant.model_copy(
                    update={
                        "allowed_recovery_actions": [
                            "RETRY_PAYMENT",
                            "STOP",
                        ]
                    }
                )
            },
        )

        response = self._mock_gemini_response(
            action="ESCALATE",
            predicted_p_recovery=0.40,
            rationale="Escalation is appropriate.",
        )

        self.client.models.generate_content.return_value = response

        with self.assertRaisesRegex(
            ValueError,
            "not in the allowed recovery actions",
        ):
            self.service.decide(restricted_context)

    def test_stop_is_valid_when_allowed(self):
        restricted_context = self.context.model_copy(
            deep=True,
            update={
                "merchant": self.context.merchant.model_copy(
                    update={
                        "allowed_recovery_actions": [
                            "RETRY_PAYMENT",
                            "STOP",
                        ]
                    }
                )
            },
        )

        response = self._mock_gemini_response(
            action="STOP",
            predicted_p_recovery=0.0,
            rationale=(
                "Further automated recovery is unlikely to succeed "
                "after the available recovery attempts."
            ),
        )

        self.client.models.generate_content.return_value = response

        decision = self.service.decide(restricted_context)

        self.assertEqual(decision.action, "STOP")
        self.assertEqual(decision.predicted_p_recovery, 0.0)

    def test_escalate_is_valid_when_allowed(self):
        restricted_context = self.context.model_copy(
            deep=True,
            update={
                "merchant": self.context.merchant.model_copy(
                    update={
                        "allowed_recovery_actions": [
                            "RETRY_PAYMENT",
                            "ESCALATE",
                            "STOP",
                        ]
                    }
                )
            },
        )

        response = self._mock_gemini_response(
            action="ESCALATE",
            predicted_p_recovery=0.35,
            rationale=(
                "Repeated automated recovery attempts indicate "
                "that escalation may provide a better recovery path."
            ),
        )

        self.client.models.generate_content.return_value = response

        decision = self.service.decide(restricted_context)

        self.assertEqual(decision.action, "ESCALATE")
        self.assertEqual(decision.predicted_p_recovery, 0.35)

    def test_probability_above_one_is_rejected(self):
        response = MagicMock()
        response.text = """
        {
            "action": "RETRY_PAYMENT",
            "predicted_p_recovery": 1.5,
            "rationale": "Invalid probability."
        }
        """

        self.client.models.generate_content.return_value = response

        with self.assertRaises(ValidationError):
            self.service.decide(self.context)

    def test_probability_below_zero_is_rejected(self):
        response = MagicMock()
        response.text = """
        {
            "action": "RETRY_PAYMENT",
            "predicted_p_recovery": -0.1,
            "rationale": "Invalid probability."
        }
        """

        self.client.models.generate_content.return_value = response

        with self.assertRaises(ValidationError):
            self.service.decide(self.context)

    def test_empty_allowed_actions_are_rejected(self):
        empty_context = self.context.model_copy(
            deep=True,
            update={
                "merchant": self.context.merchant.model_copy(
                    update={
                        "allowed_recovery_actions": []
                    }
                )
            },
        )

        with self.assertRaisesRegex(
            ValueError,
            "No allowed recovery actions provided",
        ):
            self.service.decide(empty_context)

        self.client.models.generate_content.assert_not_called()


if __name__ == "__main__":
    unittest.main()
