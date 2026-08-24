import unittest
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_db_session
from app.main import app
from app.models import RecoveryCase, RecoveryEvent


class FakeSession:
    def __init__(self, fail_on_flush=False):
        self.events = {}
        self.cases = {}
        self.pending = []
        self.fail_on_flush = fail_on_flush
        self.rollbacks = 0

    def get(self, model, key):
        return self.events.get(key) if model is RecoveryEvent else None

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
    return {
        "event_id": event_id,
        "event_type": "PAYMENT_FAILED",
        "occurred_at": "2026-08-23T12:00:00Z",
        "payment_id": "payment_001",
        "merchant_id": "merchant_001",
        "customer_id": "customer_001",
        "amount": "125.50",
        "currency": "INR",
        "failure_code": "DECLINED",
        "failure_category": "TEMPORARY_FAILURE",
        "payment_method": "CARD",
        "attempt_number": 1,
    }


class RecoveryEventApiTests(unittest.TestCase):
    def setUp(self):
        self.session = FakeSession()
        app.dependency_overrides[get_db_session] = lambda: self.session
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_creates_event_and_case(self):
        response = self.client.post("/recovery-events", json=payload())

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "created")
        self.assertEqual(len(self.session.events), 1)
        self.assertEqual(len(self.session.cases), 1)
        self.assertEqual(response.json()["recovery_case"]["status"], "PENDING")

    def test_duplicate_event_is_idempotent(self):
        self.client.post("/recovery-events", json=payload())
        response = self.client.post("/recovery-events", json=payload())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "duplicate")
        self.assertEqual(len(self.session.events), 1)
        self.assertEqual(len(self.session.cases), 1)

    def test_invalid_request_returns_validation_error(self):
        response = self.client.post("/recovery-events", json={"event_id": "event_001"})

        self.assertEqual(response.status_code, 422)

    def test_transaction_failure_rolls_back(self):
        self.session.fail_on_flush = True
        response = self.client.post("/recovery-events", json=payload())

        self.assertEqual(response.status_code, 500)
        self.assertEqual(self.session.rollbacks, 1)
        self.assertEqual(self.session.events, {})
        self.assertEqual(self.session.cases, {})


if __name__ == "__main__":
    unittest.main()
