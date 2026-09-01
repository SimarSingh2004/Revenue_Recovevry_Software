import unittest
from unittest.mock import MagicMock

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

        metrics = get_recovery_metrics(db)

        self.assertEqual(metrics["total_recovery_attempts"], 4)
        self.assertEqual(metrics["successful_recoveries"], 2)
        self.assertEqual(metrics["recovery_success_rate"], 0.5)
        self.assertEqual(metrics["total_recovered_value"], 2000.0)
        self.assertEqual(metrics["total_fee_loss"], 6.0)
        self.assertEqual(metrics["net_recovered_value"], 1994.0)


if __name__ == "__main__":
    unittest.main()