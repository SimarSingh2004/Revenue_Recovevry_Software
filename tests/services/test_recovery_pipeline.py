import unittest
from unittest.mock import MagicMock, patch

from app.models import RecoveryCase
from app.schemas.llm_decision import LLMDecision
from app.schemas.policy_decision import PolicyDecision
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
        self.policy_decision = PolicyDecision(
            approved=True,
            action="RETRY_PAYMENT",
            expected_net_recovery=42.0,
            reasons=["Expected net recovery is positive"],
        )

    @patch("app.services.recovery_pipeline.load_recovery_context")
    @patch("app.services.recovery_pipeline.retrieve_recovery_memory")
    @patch("app.services.recovery_pipeline.build_historical_insights")
    @patch("app.services.recovery_pipeline.expected_net_recovery_value")
    def test_loads_context_and_returns_policy_decision(
        self,
        mock_expected_net_recovery,
        mock_build_insights,
        mock_retrieve_memory,
        mock_load_context,
    ):
        mock_load_context.return_value = self.context
        mock_retrieve_memory.return_value = []
        mock_build_insights.return_value = []
        mock_expected_net_recovery.return_value = 42.0
        self.llm_decision_service.decide.return_value = self.decision
        policy_engine = MagicMock()
        policy_engine.evaluate.return_value = self.policy_decision

        result = run_recovery_pipeline(
            self.db,
            self.recovery_case,
            self.llm_decision_service,
            policy_engine,
        )

        mock_load_context.assert_called_once_with(self.db, "case_001")
        mock_retrieve_memory.assert_called_once_with(self.db, self.context)
        mock_build_insights.assert_called_once_with([])
        self.llm_decision_service.decide.assert_called_once_with(self.context, [])
        mock_expected_net_recovery.assert_called_once_with(
            self.context,
            "RETRY_PAYMENT",
            0.72,
        )
        policy_engine.evaluate.assert_called_once_with(
            self.context,
            "RETRY_PAYMENT",
            42.0,
        )
        self.assertIs(result, self.policy_decision)

    @patch("app.services.recovery_pipeline.load_recovery_context")
    @patch("app.services.recovery_pipeline.retrieve_recovery_memory")
    @patch("app.services.recovery_pipeline.build_historical_insights")
    @patch("app.services.recovery_pipeline.expected_net_recovery_value")
    def test_passes_context_and_safe_historical_insights_to_llm_service(
        self,
        mock_expected_net_recovery,
        mock_build_insights,
        mock_retrieve_memory,
        mock_load_context,
    ):
        mock_load_context.return_value = self.context
        mock_retrieve_memory.return_value = []
        safe_insights = [MagicMock()]
        mock_build_insights.return_value = safe_insights
        mock_expected_net_recovery.return_value = 42.0
        self.llm_decision_service.decide.return_value = self.decision
        policy_engine = MagicMock()
        policy_engine.evaluate.return_value = self.policy_decision

        run_recovery_pipeline(
            self.db,
            self.recovery_case,
            self.llm_decision_service,
            policy_engine,
        )

        self.llm_decision_service.decide.assert_called_once_with(
            self.context,
            safe_insights,
        )


if __name__ == "__main__":
    unittest.main()
