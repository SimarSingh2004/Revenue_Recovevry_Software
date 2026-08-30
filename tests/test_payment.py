import unittest
from decimal import Decimal

from app.schemas.payment import PaymentCreate
from app.simulator.payments import PaymentOutcome


class PaymentCreateTests(unittest.TestCase):

    def test_accepts_success_simulation(self):
        payment = PaymentCreate(
            payment_id="payment_001",
            merchant_id="merchant_001",
            customer_id="customer_001",
            amount=Decimal("1250.00"),
            currency="INR",
            payment_method="CARD",
            simulation_outcome=PaymentOutcome.SUCCESS,
        )

        self.assertEqual(payment.simulation_outcome, PaymentOutcome.SUCCESS)

    def test_accepts_failed_simulation(self):
        payment = PaymentCreate(
            payment_id="payment_001",
            merchant_id="merchant_001",
            customer_id="customer_001",
            amount=Decimal("1250.00"),
            currency="INR",
            payment_method="CARD",
            simulation_outcome=PaymentOutcome.FAILED,
        )

        self.assertEqual(payment.simulation_outcome, PaymentOutcome.FAILED)


if __name__ == "__main__":
    unittest.main()