import unittest

from app.core.recovery_actions import (
    ACTION_COSTS,
    PAYMENT_ATTEMPT_BEHAVIOR,
    RecoveryAction,
    get_action_cost,
    get_payment_attempt_behavior,
)


class RecoveryActionTests(unittest.TestCase):
    def test_contains_exactly_the_finalized_actions(self):
        self.assertEqual(
            set(RecoveryAction),
            {
                RecoveryAction.RETRY_PAYMENT,
                RecoveryAction.ALTERNATE_PAYMENT_METHOD,
                RecoveryAction.SEND_PAYMENT_LINK,
                RecoveryAction.ESCALATE,
                RecoveryAction.STOP,
            },
        )

    def test_actions_have_the_correct_costs(self):
        self.assertEqual(
            ACTION_COSTS,
            {
                RecoveryAction.RETRY_PAYMENT: 2,
                RecoveryAction.ALTERNATE_PAYMENT_METHOD: 3,
                RecoveryAction.SEND_PAYMENT_LINK: 1,
                RecoveryAction.ESCALATE: 5,
                RecoveryAction.STOP: 0,
            },
        )

    def test_get_action_cost(self):
        self.assertEqual(get_action_cost(RecoveryAction.RETRY_PAYMENT), 2)
        self.assertEqual(get_action_cost("STOP"), 0)

    def test_unknown_action_is_rejected(self):
        with self.assertRaises(ValueError):
            get_action_cost("CALL_CUSTOMER")

    def test_payment_attempt_behavior(self):
        self.assertEqual(
            get_payment_attempt_behavior(RecoveryAction.RETRY_PAYMENT),
            "ON_ACTUAL_PAYMENT_ATTEMPT",
        )
        self.assertEqual(
            get_payment_attempt_behavior(RecoveryAction.ALTERNATE_PAYMENT_METHOD),
            "ON_ACTUAL_PAYMENT_ATTEMPT",
        )
        self.assertEqual(
            get_payment_attempt_behavior(RecoveryAction.SEND_PAYMENT_LINK),
            "ON_CUSTOMER_PAYMENT_ATTEMPT_VIA_LINK",
        )
        self.assertEqual(
            get_payment_attempt_behavior(RecoveryAction.ESCALATE),
            "DOES_NOT_INCREMENT",
        )
        self.assertEqual(
            get_payment_attempt_behavior(RecoveryAction.STOP),
            "DOES_NOT_INCREMENT",
        )


if __name__ == "__main__":
    unittest.main()