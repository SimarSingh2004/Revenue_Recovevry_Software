import unittest

from app.simulator.payments import (
    PaymentOutcome,
    PaymentSimulator,
)


class PaymentSimulatorTests(unittest.TestCase):

    def setUp(self):
        self.simulator = PaymentSimulator()

    def test_simulates_successful_payment(self):
        result = self.simulator.process(
            "payment_001",
            outcome=PaymentOutcome.SUCCESS,
        )

        self.assertEqual(result.payment_id, "payment_001")
        self.assertEqual(result.outcome, PaymentOutcome.SUCCESS)

    def test_simulates_failed_payment(self):
        result = self.simulator.process(
            "payment_001",
            outcome=PaymentOutcome.FAILED,
        )

        self.assertEqual(result.payment_id, "payment_001")
        self.assertEqual(result.outcome, PaymentOutcome.FAILED)


if __name__ == "__main__":
    unittest.main()