from datetime import datetime, timezone
from decimal import Decimal
import unittest
from unittest.mock import MagicMock

from app.models import RecoveryLearningMemory
from app.schemas.recovery_context import (
    CurrentPaymentFailureContext,
    CustomerPaymentHistoryContext,
    MerchantContextData,
    MerchantRecoveryHistoryContext,
    RecoveryCaseContext,
    RecoveryContext,
)
from app.services.recovery_memory import (
    build_historical_insights,
    retrieve_recovery_memory,
    store_recovery_memory,
)


class RecoveryMemoryTests(unittest.TestCase):

    def setUp(self):
        now = datetime(2026, 8, 26, tzinfo=timezone.utc)
        self.context = RecoveryContext(
            case=RecoveryCaseContext(
                case_id="case_001", event_id="event_001", payment_id="payment_001",
                status="PENDING", case_created_at=now,
            ),
            current_payment_failure=CurrentPaymentFailureContext(
                customer_id="customer_001", amount=Decimal("100.00"), currency="INR",
                event_type="PAYMENT_FAILED", event_occurred_at=now,
                failure_code="DECLINED", failure_category="TEMPORARY_FAILURE",
                payment_method="CARD", payment_attempt_number=2,
            ),
            merchant=MerchantContextData(
                merchant_id="merchant_001", recovery_enabled=True,
                allowed_recovery_actions=["RETRY_PAYMENT"], merchant_segment="SMB",
                retry_cooldown_seconds=60, max_recovery_attempts=3,
            ),
            merchant_recovery_history=MerchantRecoveryHistoryContext(
                history=[], recovery_attempt_count=0, last_recovery_action=None,
                last_recovery_outcome=None, last_recovery_at=None,
            ),
            customer_payment_history=CustomerPaymentHistoryContext(
                historical_payments=[], customer_payment_count=0,
                customer_failed_payment_count=0, customer_successful_payment_count=0,
                customer_failure_rate=Decimal("0"),
            ),
        )

    def memory(
        self,
        identifier: int,
        action: str,
        outcome: str,
        *,
        failure_code: str = "DECLINED",
        failure_category: str = "TEMPORARY_FAILURE",
        payment_method: str = "CARD",
        payment_attempt_number: int = 2,
    ) -> RecoveryLearningMemory:
        return RecoveryLearningMemory(
            id=identifier,
            failure_code=failure_code,
            failure_category=failure_category,
            payment_method=payment_method,
            payment_attempt_number=payment_attempt_number,
            action=action,
            outcome=outcome,
            llm_p_pred=Decimal("0.60"),
            gt_p=Decimal("0.50"),
            baseline_p=Decimal("0.40"),
            net_recovery_value=Decimal("50.00"),
            financial_impact="POSITIVE_RECOVERY",
        )

    def retrieve(self, records):
        db = MagicMock()
        db.scalars.return_value = iter(records)
        return retrieve_recovery_memory(db, self.context)

    def test_completed_memory_record_is_stored(self):
        db = MagicMock()

        memory = store_recovery_memory(
            db,
            failure_code="DECLINED",
            failure_category="TEMPORARY_FAILURE",
            payment_method="CARD",
            payment_attempt_number=2,
            action="RETRY_PAYMENT",
            outcome="SUCCESS",
            llm_p_pred=Decimal("0.60"),
            gt_p=Decimal("0.50"),
            baseline_p=Decimal("0.40"),
            net_recovery_value=Decimal("50.00"),
            financial_impact="POSITIVE_RECOVERY",
        )

        db.add.assert_called_once_with(memory)
        db.commit.assert_called_once_with()
        db.refresh.assert_called_once_with(memory)
        self.assertEqual(memory.action, "RETRY_PAYMENT")
        self.assertEqual(memory.gt_p, Decimal("0.50"))

    def test_exact_matching_prefers_success_and_failed_actions(self):
        records = [
            self.memory(1, "RETRY_PAYMENT", "FAILED"),
            self.memory(2, "SEND_PAYMENT_LINK", "SUCCESS"),
            self.memory(3, "ESCALATE", "FAILED"),
            self.memory(4, "RETRY_PAYMENT", "SUCCESS"),
        ]

        selected = self.retrieve(records)

        self.assertEqual(len(selected), 3)
        self.assertIn("SUCCESS", [record.outcome for record in selected])
        self.assertIn("FAILED", [record.outcome for record in selected])
        self.assertEqual(len({record.action for record in selected}), len(selected))

    def test_attempt_fallback_and_category_fallback_are_used_only_when_needed(self):
        attempt_fallback = self.memory(
            1, "RETRY_PAYMENT", "SUCCESS", payment_attempt_number=3
        )
        category_fallback = self.memory(
            2, "SEND_PAYMENT_LINK", "FAILED", failure_code="OTHER",
            payment_method="UPI", payment_attempt_number=9,
        )
        unrelated = self.memory(
            3, "ESCALATE", "FAILED", failure_code="OTHER",
            failure_category="OTHER_CATEGORY", payment_method="UPI",
            payment_attempt_number=9,
        )

        selected = self.retrieve([attempt_fallback, category_fallback, unrelated])

        self.assertEqual(selected, [attempt_fallback, category_fallback])

    def test_retrieval_is_limited_to_three_records(self):
        records = [
            self.memory(1, "RETRY_PAYMENT", "SUCCESS"),
            self.memory(2, "SEND_PAYMENT_LINK", "FAILED"),
            self.memory(3, "ESCALATE", "FAILED"),
            self.memory(4, "ALTERNATE_PAYMENT_METHOD", "FAILED"),
        ]

        self.assertEqual(len(self.retrieve(records)), 3)

    def test_historical_insights_exclude_evaluation_values(self):
        insights = build_historical_insights([
            self.memory(1, "RETRY_PAYMENT", "SUCCESS"),
        ])

        self.assertEqual(len(insights), 1)
        self.assertEqual(
            set(insights[0].model_dump()),
            {
                "failure_code", "failure_category", "payment_method",
                "payment_attempt_number", "action", "outcome",
                "financial_impact",
            },
        )


if __name__ == "__main__":
    unittest.main()
