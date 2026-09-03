import unittest
from unittest.mock import MagicMock
from decimal import Decimal
from types import SimpleNamespace

from app.services.recovery_metrics import get_recovery_metrics


class RecoveryMetricsTests(unittest.TestCase):

    def test_returns_recovery_metrics(self):
        db = MagicMock()

        db.query.return_value.filter.return_value.filter.return_value.scalar.side_effect = [
            4,      
        ]

        db.query.return_value.filter.return_value.scalar.side_effect = [
            2,       
            2000.0,  
            -6.0,      
        ]

        db.query.return_value.scalar.return_value=1994.0

        db.query.return_value.filter.return_value.all.return_value = [
            SimpleNamespace(llm_p_pred=Decimal("0.80"), gt_p=Decimal("0.75"), baseline_p=Decimal("0.65")),
            SimpleNamespace(llm_p_pred=Decimal("0.40"), gt_p=Decimal("0.50"), baseline_p=Decimal("0.55")),
        ]

        metrics = get_recovery_metrics(db)

        self.assertEqual(metrics["total_recovery_attempts"], 4)
        self.assertEqual(metrics["successful_recoveries"], 2)
        self.assertEqual(metrics["recovery_success_rate"], 0.5)
        self.assertEqual(metrics["total_recovered_value"], 2000.0)
        self.assertEqual(metrics["total_fee_loss"], 6.0)
        self.assertEqual(metrics["net_recovered_value"], 1994.0)
        self.assertEqual(metrics["llm_error"], 0.075)
        self.assertEqual(metrics["baseline_error"], 0.075)

    def test_calibration_none_when_no_attempts(self):
        db=MagicMock()

        db.query.return_value.filter.return_value.filter.return_value.scalar.side_effect = [0]
        db.query.return_value.filter.return_value.scalar.side_effect = [0, 0.0, 0.0]
        db.query.return_value.scalar.return_value = 0.0
        db.query.return_value.filter.return_value.all.return_value = []

        metrics = get_recovery_metrics(db)

        self.assertIsNone(metrics["llm_error"])
        self.assertIsNone(metrics["baseline_error"])


if __name__ == "__main__":
    unittest.main()