import unittest
from unittest.mock import ANY, MagicMock, patch
from app.core.recovery_actions import RecoveryAction
from app.models import RecoveryCase
from app.schemas.llm_decision import LLMDecision
from app.schemas.policy_decision import PolicyDecision
from app.services.recovery_pipeline import run_recovery_pipeline
from app.simulator.payment_provider import (
    PaymentProviderSimulator,
    SimulationOutcome,
    SimulationResult,
)


@patch("app.services.recovery_pipeline.get_action_cost", return_value=1.5)
@patch("app.services.recovery_pipeline.load_recovery_context")
@patch("app.services.recovery_pipeline.retrieve_recovery_memory")
@patch("app.services.recovery_pipeline.build_historical_insights")
@patch("app.services.recovery_pipeline.expected_net_recovery_value")
class RecoveryPipelineTests(unittest.TestCase):

    def setUp(self):
        self.db = MagicMock()
        self.recovery_case = RecoveryCase(case_id="case_001")
        self.llm_decision_service = MagicMock()
        self.policy_engine = MagicMock()
        self.context = MagicMock()

        self.context.merchant.merchant_id = "merchant_001"
        self.context.case.case_id = "case_001"
        self.context.current_payment_failure.amount = 1250

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
        self.policy_engine.evaluate.return_value = self.policy_decision

        self.simulation_result = SimulationResult(
            action=RecoveryAction.RETRY_PAYMENT,
            outcome=SimulationOutcome.SUCCESS,
            is_payment_attempt=True,
            is_provider_execution=True,
            provider_reference="sim_retry_payment_payment_001_1",
        )
        self.payment_provider = MagicMock(spec=PaymentProviderSimulator)
        self.payment_provider.execute.return_value = self.simulation_result

    def test_loads_context_and_returns_policy_decision(
        self,
        mock_expected_net_recovery,
        mock_build_insights,
        mock_retrieve_memory,
        mock_load_context,
        mock_get_action_cost,
    ):
        mock_load_context.return_value = self.context
        mock_retrieve_memory.return_value = []
        mock_build_insights.return_value = []
        mock_expected_net_recovery.return_value = 42.0
        self.llm_decision_service.decide.return_value = self.decision

        policy_decision, simulation_result = run_recovery_pipeline(
            db=self.db,
            recovery_case=self.recovery_case,
            llm_decision_service=self.llm_decision_service,
            policy_engine=self.policy_engine,
            payment_provider=self.payment_provider,
            success_probability=0.5,
        )

        mock_load_context.assert_called_once_with(self.db, "case_001")
        mock_retrieve_memory.assert_called_once_with(self.db, self.context)
        mock_build_insights.assert_called_once_with([])
        self.llm_decision_service.decide.assert_called_once_with(self.context, [])
        mock_expected_net_recovery.assert_called_once_with(self.context, "RETRY_PAYMENT", 0.72)
        self.policy_engine.evaluate.assert_called_once_with(self.context, "RETRY_PAYMENT", 42.0, now=ANY)
        self.assertIs(policy_decision, self.policy_decision)

    def test_passes_context_and_safe_historical_insights_to_llm_service(
        self,
        mock_expected_net_recovery,
        mock_build_insights,
        mock_retrieve_memory,
        mock_load_context,
        mock_get_action_cost,
    ):
        mock_load_context.return_value = self.context
        mock_retrieve_memory.return_value = []
        safe_insights = [MagicMock()]
        mock_build_insights.return_value = safe_insights
        mock_expected_net_recovery.return_value = 42.0
        self.llm_decision_service.decide.return_value = self.decision

        run_recovery_pipeline(
            db=self.db,
            recovery_case=self.recovery_case,
            llm_decision_service=self.llm_decision_service,
            policy_engine=self.policy_engine,
            payment_provider=self.payment_provider,
            success_probability=0.5,
        )

        self.llm_decision_service.decide.assert_called_once_with(self.context, safe_insights)

    def test_executes_approved_action_and_stores_merchant_history(
        self,
        mock_expected_net_recovery,
        mock_build_historical_insights,
        mock_retrieve_recovery_memory,
        mock_load_context,
        mock_get_action_cost,
    ):
        mock_load_context.return_value = self.context
        mock_retrieve_recovery_memory.return_value = []
        mock_build_historical_insights.return_value = []
        mock_expected_net_recovery.return_value = 748.0
        self.llm_decision_service.decide.return_value = self.decision

        policy_decision, simulation_result = run_recovery_pipeline(
            db=self.db,
            recovery_case=self.recovery_case,
            llm_decision_service=self.llm_decision_service,
            policy_engine=self.policy_engine,
            payment_provider=self.payment_provider,
            success_probability=0.60,
        )

        self.payment_provider.execute.assert_called_once_with("RETRY_PAYMENT", self.context, success_probability=0.60)
        self.db.add.assert_called_once()
        self.db.commit.assert_called_once()

        history_record = self.db.add.call_args.args[0]
        self.assertEqual(history_record.merchant_id, "merchant_001")
        self.assertEqual(history_record.case_id, "case_001")
        self.assertEqual(history_record.action, "RETRY_PAYMENT")
        self.assertEqual(history_record.outcome, "SUCCESS")
        self.assertEqual(history_record.amount, 1250)
        self.assertIs(simulation_result, self.simulation_result)

    def test_does_not_execute_or_store_when_policy_rejects(
        self,
        mock_expected_net_recovery,
        mock_build_historical_insights,
        mock_retrieve_recovery_memory,
        mock_load_context,
        mock_get_action_cost,
    ):
        mock_load_context.return_value = self.context
        mock_retrieve_recovery_memory.return_value = []
        mock_build_historical_insights.return_value = []
        mock_expected_net_recovery.return_value = -10.0
        self.llm_decision_service.decide.return_value = self.decision

        rejected_policy_decision = PolicyDecision(
            approved=False,
            action="RETRY_PAYMENT",
            expected_net_recovery=0.0,
            reasons=["Expected net recovery must be positive."],
        )
        self.policy_engine.evaluate.return_value = rejected_policy_decision

        policy_decision, simulation_result = run_recovery_pipeline(
            db=self.db,
            recovery_case=self.recovery_case,
            llm_decision_service=self.llm_decision_service,
            policy_engine=self.policy_engine,
            payment_provider=self.payment_provider,
            success_probability=0.60,
        )

        self.payment_provider.execute.assert_not_called()
        self.db.add.assert_not_called()
        self.db.commit.assert_not_called()
        self.assertIs(policy_decision, rejected_policy_decision)
        self.assertIsNone(simulation_result)


if __name__ == "__main__":
    unittest.main()