import unittest

from app.core.recovery_actions import RecoveryAction
from app.services.payment_attempts import increment_payment_attempt_number
from tests.simulator.test_ground_truth import make_context


class PaymentAttemptNumberTests(unittest.TestCase):
    def test_payment_actions_increment_the_context_number(self):
        for action in (
            RecoveryAction.RETRY_PAYMENT,
            RecoveryAction.ALTERNATE_PAYMENT_METHOD,
            RecoveryAction.SEND_PAYMENT_LINK,
        ):
            with self.subTest(action=action):
                context = make_context()
                self.assertEqual(increment_payment_attempt_number(context, action), 2)
                self.assertEqual(context.current_payment_failure.payment_attempt_number, 2)

    def test_non_payment_actions_do_not_increment_the_context_number(self):
        for action in (RecoveryAction.ESCALATE, RecoveryAction.STOP):
            with self.subTest(action=action):
                context = make_context()
                self.assertEqual(increment_payment_attempt_number(context, action), 1)

    def test_invalid_action_is_rejected(self):
        with self.assertRaises(ValueError):
            increment_payment_attempt_number(make_context(), "CALL_CUSTOMER")
