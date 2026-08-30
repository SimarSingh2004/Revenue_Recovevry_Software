import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.models import RecoveryCase, RecoveryEvent
from app.schemas import RecoveryEventCreate
from app.services.recovery_event import create_recovery_event_service


class FakeSession:
    def __init__(self, fail_on_flush=False):
        self.events = {}
        self.cases = {}
        self.pending = []
        self.fail_on_flush = fail_on_flush
        self.rollbacks = 0

    def get(self, model, key):
        if model is RecoveryEvent:
            return self.events.get(key)
        return None

    def scalar(self, statement):
        return next(iter(self.cases.values()), None)

    def add(self, instance):
        self.pending.append(instance)

    def flush(self):
        if self.fail_on_flush:
            raise SQLAlchemyError("flush failed")

    def commit(self):
        for instance in self.pending:
            if isinstance(instance, RecoveryEvent):
                self.events[instance.event_id] = instance
            if isinstance(instance, RecoveryCase):
                self.cases[instance.event_id] = instance
        self.pending = []

    def refresh(self, instance):
        now = datetime.now(timezone.utc)

        if instance.created_at is None:
            instance.created_at = now

        if isinstance(instance, RecoveryCase) and instance.updated_at is None:
            instance.updated_at = now

    def rollback(self):
        self.rollbacks += 1
        self.pending = []


def payload(event_id="event_001"):
    return RecoveryEventCreate(
        event_id=event_id,
        event_type="PAYMENT_FAILED",
        occurred_at=datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc),
        payment_id="payment_001",
        merchant_id="merchant_001",
        customer_id="customer_001",
        amount="125.50",
        currency="INR",
        failure_code="DECLINED",
        failure_category="TEMPORARY_FAILURE",
        payment_method="CARD",
    )


class RecoveryEventServiceTests(unittest.TestCase):

    def setUp(self):
        self.session = FakeSession()
        self.llm_decision_service = MagicMock()
        self.policy_engine = MagicMock()
        self.payment_provider = MagicMock()

    @patch("app.services.recovery_event.run_recovery_until_resolved")
    def test_creates_event_and_case(self, mock_recovery):
        result = create_recovery_event_service(
            payload=payload(),
            db=self.session,
            llm_decision_service=self.llm_decision_service,
            policy_engine=self.policy_engine,
            payment_provider=self.payment_provider,
        )

        self.assertEqual(result.status, "created")
        self.assertEqual(len(self.session.events), 1)
        self.assertEqual(len(self.session.cases), 1)

        mock_recovery.assert_called_once()

        call_kwargs = mock_recovery.call_args.kwargs

        self.assertIs(
            call_kwargs["recovery_case"],
            next(iter(self.session.cases.values())),
        )

    @patch("app.services.recovery_event.run_recovery_until_resolved")
    def test_duplicate_event_is_idempotent(self, mock_recovery):
        first_result = create_recovery_event_service(
            payload=payload(),
            db=self.session,
            llm_decision_service=self.llm_decision_service,
            policy_engine=self.policy_engine,
            payment_provider=self.payment_provider,
        )

        second_result = create_recovery_event_service(
            payload=payload(),
            db=self.session,
            llm_decision_service=self.llm_decision_service,
            policy_engine=self.policy_engine,
            payment_provider=self.payment_provider,
        )

        self.assertEqual(first_result.status, "created")
        self.assertEqual(second_result.status, "duplicate")

        self.assertEqual(len(self.session.events), 1)
        self.assertEqual(len(self.session.cases), 1)

        mock_recovery.assert_called_once()

    def test_transaction_failure_rolls_back(self):
        self.session.fail_on_flush = True

        with self.assertRaises(HTTPException) as context:
            create_recovery_event_service(
                payload=payload(),
                db=self.session,
                llm_decision_service=self.llm_decision_service,
                policy_engine=self.policy_engine,
                payment_provider=self.payment_provider,
            )

        self.assertEqual(self.session.rollbacks, 1)
        self.assertEqual(self.session.events, {})
        self.assertEqual(self.session.cases, {})

        self.assertEqual(context.exception.status_code, 500)


if __name__ == "__main__":
    unittest.main()