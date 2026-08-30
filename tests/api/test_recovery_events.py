import unittest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.db.session import get_db_session
from app.main import app
from app.models import RecoveryCase, RecoveryEvent
from app.schemas import RecoveryEventIngestionResponse


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


def recovery_response(status: str) -> RecoveryEventIngestionResponse:
    event = RecoveryEvent(
        event_id="event_001",
        event_type="PAYMENT_FAILED",
        occurred_at=datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc),
        payment_id="payment_001",
        merchant_id="merchant_001",
        customer_id="customer_001",
        amount=Decimal("125.50"),
        currency="INR",
        failure_code="DECLINED",
        failure_category="TEMPORARY_FAILURE",
        payment_method="CARD",
        attempt_number=1,
        created_at=datetime(2026, 8, 23, 12, 1, tzinfo=timezone.utc),
    )

    case = RecoveryCase(
        case_id="case_001",
        event_id="event_001",
        payment_id="payment_001",
        status="PENDING",
        created_at=datetime(2026, 8, 23, 12, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 8, 23, 12, 1, tzinfo=timezone.utc),
    )

    return RecoveryEventIngestionResponse(
        status=status,
        recovery_event=event,
        recovery_case=case,
    )


class RecoveryEventApiTests(unittest.TestCase):

    def setUp(self):
        self.db = MagicMock()
        app.dependency_overrides[get_db_session] = lambda: self.db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    @patch("app.api.recovery_events.create_recovery_event_service")
    def test_create_recovery_event_delegates_to_service(
        self,
        mock_service,
    ):
        mock_service.return_value = recovery_response("created")

        response = self.client.post(
            "/recovery-events",
            json=payload(),
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "created")
        mock_service.assert_called_once()

    @patch("app.api.recovery_events.create_recovery_event_service")
    def test_duplicate_event_returns_200(
        self,
        mock_service,
    ):
        mock_service.return_value = recovery_response("duplicate")

        response = self.client.post(
            "/recovery-events",
            json=payload(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "duplicate")
        mock_service.assert_called_once()

    def test_invalid_request_returns_validation_error(self):
        response = self.client.post(
            "/recovery-events",
            json={"event_id": "event_001"},
        )

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()