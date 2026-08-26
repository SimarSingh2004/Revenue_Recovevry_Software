import unittest
from unittest.mock import MagicMock, patch

from app.models import RecoveryCase
from app.schemas.llm_decision import LLMDecision
from app.services.recovery_pipeline import run_recovery_pipeline


class RecoveryPipelineTests(unittest.TestCase):

    def setUp(self):
        self.db = MagicMock()
        self.recovery_case = RecoveryCase(case_id="case_001")
        self.llm_decision_service = MagicMock()
        self.context = MagicMock()
        self.decision = LLMDecision(
            action="RETRY_PAYMENT",
            predicted_p_recovery=0.72,
            rationale="Retry is appropriate.",
        )

    @patch("app.services.recovery_pipeline.load_recovery_context")
    def test_loads_context_and_returns_llm_decision_unchanged(self, mock_load_context):
        mock_load_context.return_value = self.context
        self.llm_decision_service.decide.return_value = self.decision

        result = run_recovery_pipeline(
            self.db,
            self.recovery_case,
            self.llm_decision_service,
        )

        mock_load_context.assert_called_once_with(self.db, "case_001")
        self.llm_decision_service.decide.assert_called_once_with(self.context)
        self.assertIs(result, self.decision)

    @patch("app.services.recovery_pipeline.load_recovery_context")
    def test_passes_only_recovery_context_to_llm_service(self, mock_load_context):
        mock_load_context.return_value = self.context
        self.llm_decision_service.decide.return_value = self.decision

        run_recovery_pipeline(
            self.db,
            self.recovery_case,
            self.llm_decision_service,
        )

        self.llm_decision_service.decide.assert_called_once_with(self.context)


if __name__ == "__main__":
    unittest.main()
