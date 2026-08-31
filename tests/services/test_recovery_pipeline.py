import unittest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import ANY, MagicMock, patch
from app.core.recovery_actions import RecoveryAction
from app.models import RecoveryCase
from app.schemas.llm_decision import LLMDecision
from app.schemas.policy_decision import PolicyDecision
from app.services.recovery_pipeline import (run_recovery_pipeline,
    run_recovery_until_resolved)
from app.simulator.payment_provider import (
    PaymentProviderSimulator,
    SimulationOutcome,
    SimulationResult,
)
from app.simulator.ground_truth import ground_truth_probability


@patch("app.services.recovery_pipeline.get_action_cost", return_value=1.5)
@patch("app.services.recovery_pipeline.load_recovery_context")
@patch("app.services.recovery_pipeline.retrieve_recovery_memory")
@patch("app.services.recovery_pipeline.build_historical_insights")
@patch("app.services.recovery_pipeline.expected_net_recovery_value")
@patch("app.services.recovery_pipeline.ground_truth_probability", return_value=0.60)

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
        self.context.current_payment_failure.failure_code = "CARD_DECLINED"
        self.context.current_payment_failure.failure_category = "TEMPORARY_FAILURE"
        self.context.current_payment_failure.payment_method = "CARD"
        self.context.current_payment_failure.payment_attempt_number = 1
        self.context.current_payment_failure.event_occurred_at = (
            datetime.now(timezone.utc) - timedelta(minutes=5)
        )

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

        self.baseline_probability_patcher = patch(
            "app.services.recovery_memory.baseline_probability",
            return_value=0.55,
        )
        self.mock_baseline_probability = self.baseline_probability_patcher.start()
        self.addCleanup(self.baseline_probability_patcher.stop)

        self.action_cost_patcher = patch(
            "app.services.recovery_memory.get_action_cost",
            return_value=1.5,
        )
        self.mock_memory_action_cost = self.action_cost_patcher.start()
        self.addCleanup(self.action_cost_patcher.stop)

    def test_loads_context_and_returns_policy_decision(
        self,
        mock_ground_truth_probability,
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
        )

        mock_load_context.assert_called_once_with(self.db, "case_001")
        mock_retrieve_memory.assert_called_once_with(self.db, self.context)
        mock_build_insights.assert_called_once_with([])
        self.llm_decision_service.decide.assert_called_once_with(self.context,[],policy_feedback=[])
        mock_expected_net_recovery.assert_called_once_with(self.context, "RETRY_PAYMENT", 0.72)
        self.policy_engine.evaluate.assert_called_once_with(self.context, "RETRY_PAYMENT", 42.0, now=ANY)
        self.assertIs(policy_decision, self.policy_decision)
        mock_ground_truth_probability.assert_called_once_with(self.context, RecoveryAction.RETRY_PAYMENT,now=ANY)

    def test_passes_context_and_safe_historical_insights_to_llm_service(
        self,
        mock_ground_truth_probability,
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
        )

        self.llm_decision_service.decide.assert_called_once_with(self.context, safe_insights,policy_feedback=[])

    def test_executes_approved_action_and_stores_merchant_history(
        self,
        mock_ground_truth_probability,
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
        )

        mock_ground_truth_probability.assert_called_once_with(self.context, RecoveryAction.RETRY_PAYMENT,now=ANY)

        self.payment_provider.execute.assert_called_once_with("RETRY_PAYMENT", self.context, success_probability=0.60)
        self.assertEqual(self.db.add.call_count, 2)
        self.assertEqual(self.db.commit.call_count, 2)

        added_records = [
            call.args[0]
            for call in self.db.add.call_args_list
        ]

        learning_memory = next(
            record
            for record in added_records
            if record.__class__.__name__ == "RecoveryLearningMemory"
        )

        history_record = next(
            record
            for record in added_records
            if record.__class__.__name__ == "MerchantHistory"
        )

        self.assertEqual(learning_memory.failure_code, "CARD_DECLINED")
        self.assertEqual(learning_memory.failure_category, "TEMPORARY_FAILURE")
        self.assertEqual(learning_memory.payment_method, "CARD")
        self.assertEqual(learning_memory.action, "RETRY_PAYMENT")
        self.assertEqual(learning_memory.outcome, "SUCCESS")
        self.assertEqual(learning_memory.llm_p_pred, Decimal("0.72"))
        self.assertEqual(learning_memory.gt_p, Decimal("0.60"))
        self.assertEqual(learning_memory.baseline_p, Decimal(str(
            self.mock_baseline_probability.return_value
        )))
        self.assertEqual(
            learning_memory.net_recovery_value,
            Decimal("1248.5"),
        )
        self.assertEqual(
            learning_memory.financial_impact,
            "POSITIVE_RECOVERY",
        )
        self.assertEqual(history_record.merchant_id, "merchant_001")
        self.assertEqual(history_record.case_id, "case_001")
        self.assertEqual(history_record.action, "RETRY_PAYMENT")
        self.assertEqual(history_record.outcome, "SUCCESS")
        self.assertEqual(history_record.amount, 1250)
        self.assertIs(simulation_result, self.simulation_result)

    def test_does_not_execute_or_store_when_policy_rejects(
        self,
        mock_ground_truth_probability,
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
        )

        self.payment_provider.execute.assert_not_called()
        mock_ground_truth_probability.assert_not_called()
        self.db.add.assert_not_called()
        self.db.commit.assert_not_called()
        self.assertIs(policy_decision, rejected_policy_decision)
        self.assertIsNone(simulation_result)

    def test_reprompts_llm_after_policy_rejection(
        self,
        mock_ground_truth_probability,
        mock_expected_net_recovery,
        mock_build_historical_insights,
        mock_retrieve_memory,
        mock_load_context,
        mock_get_action_cost,
    ):
        mock_load_context.return_value = self.context
        mock_retrieve_memory.return_value = []
        mock_build_historical_insights.return_value = []

        first_decision = LLMDecision(
            action="RETRY_PAYMENT",
            predicted_p_recovery=0.30,
            rationale="Retry may work.",
        )

        second_decision = LLMDecision(
            action="SEND_PAYMENT_LINK",
            predicted_p_recovery=0.70,
            rationale="Payment link is a lower-cost alternative.",
        )

        self.llm_decision_service.decide.side_effect = [
            first_decision,
            second_decision,
        ]

        first_policy = PolicyDecision(
            approved=False,
            action="RETRY_PAYMENT",
            expected_net_recovery=0.0,
            reasons=["Expected net recovery must be positive."],
        )

        second_policy = PolicyDecision(
            approved=True,
            action="SEND_PAYMENT_LINK",
            expected_net_recovery=40.0,
            reasons=["Expected net recovery is positive."],
        )

        self.policy_engine.evaluate.side_effect = [
            first_policy,
            second_policy,
        ]

        mock_expected_net_recovery.side_effect = [0.0, 40.0]

        policy_decision, simulation_result = run_recovery_pipeline(
            db=self.db,
            recovery_case=self.recovery_case,
            llm_decision_service=self.llm_decision_service,
            policy_engine=self.policy_engine,
            payment_provider=self.payment_provider,
        )

        self.assertIs(policy_decision, second_policy)

        self.assertIs(simulation_result, self.simulation_result)

        self.assertEqual(
            self.llm_decision_service.decide.call_count,
            2,
        )

        second_call = self.llm_decision_service.decide.call_args_list[1]

        self.assertEqual(
            second_call.kwargs["policy_feedback"],
            [
                {
                    "action": "RETRY_PAYMENT",
                    "reasons": [
                        "Expected net recovery must be positive."
                    ],
                }
            ],
        )


    def test_policy_retries_are_bounded(
        self,
        mock_ground_truth_probability,
        mock_expected_net_recovery,
        mock_build_historical_insights,
        mock_retrieve_memory,
        mock_load_context,
        mock_get_action_cost,
    ):
        mock_load_context.return_value = self.context
        mock_retrieve_memory.return_value = []
        mock_build_historical_insights.return_value = []

        rejected_decision = LLMDecision(
            action="RETRY_PAYMENT",
            predicted_p_recovery=0.30,
            rationale="Retry may work.",
        )

        self.llm_decision_service.decide.return_value = rejected_decision

        rejected_policy = PolicyDecision(
            approved=False,
            action="RETRY_PAYMENT",
            expected_net_recovery=0.0,
            reasons=["Expected net recovery must be positive."],
        )

        self.policy_engine.evaluate.return_value = rejected_policy
        mock_expected_net_recovery.return_value = 0.0

        policy_decision, simulation_result = run_recovery_pipeline(
            db=self.db,
            recovery_case=self.recovery_case,
            llm_decision_service=self.llm_decision_service,
            policy_engine=self.policy_engine,
        )

        self.assertIs(policy_decision, rejected_policy)
        self.assertIsNone(simulation_result)

        self.assertEqual(
            self.llm_decision_service.decide.call_count,
            3,
        )

        self.payment_provider.execute.assert_not_called()

        mock_ground_truth_probability.assert_not_called()


    def test_failed_recovery_runs_same_case_again(
            self,
            mock_ground_truth_probability,
            mock_expected_net_recovery,
            mock_build_historical_insights,
            mock_retrieve_memory,
            mock_load_context,
            mock_get_action_cost,
    ):
        first_result = SimulationResult(
            action=RecoveryAction.RETRY_PAYMENT,
            outcome=SimulationOutcome.FAILED,
            is_payment_attempt=True,
            is_provider_execution=True,
            provider_reference="sim_retry_payment_payment_001_1",
        )

        second_result = SimulationResult(
            action=RecoveryAction.SEND_PAYMENT_LINK,
            outcome=SimulationOutcome.SUCCESS,
            is_payment_attempt=True,
            is_provider_execution=True,
            provider_reference="sim_send_payment_link_payment_001_2",
        )

        first_policy = PolicyDecision(
            approved=True,
            action="RETRY_PAYMENT",
            expected_net_recovery=20.0,
            reasons=["Expected net recovery is positive"],
        )

        second_policy = PolicyDecision(
            approved=True,
            action="SEND_PAYMENT_LINK",
            expected_net_recovery=30.0,
            reasons=["Expected net recovery is positive"],
        )

        with patch(
            "app.services.recovery_pipeline.run_recovery_pipeline",
            side_effect=[
                (first_policy, first_result),
                (second_policy, second_result),
            ],
        ) as mock_pipeline:

            policy_decision, simulation_result = run_recovery_until_resolved(
                db=self.db,
                recovery_case=self.recovery_case,
                llm_decision_service=self.llm_decision_service,
                policy_engine=self.policy_engine,
                payment_provider=self.payment_provider,
            )

        self.assertIs(policy_decision, second_policy)
        self.assertIs(simulation_result, second_result)

        self.assertEqual(mock_pipeline.call_count, 2)

        first_call = mock_pipeline.call_args_list[0]
        second_call = mock_pipeline.call_args_list[1]

        self.assertIs(
            first_call.args[1],
            self.recovery_case,
        )

        self.assertIs(
            second_call.args[1],
            self.recovery_case,
        )

    def test_successful_recovery_stops_without_second_cycle(
            self,
            mock_ground_truth_probability,
            mock_expected_net_recovery,
            mock_build_historical_insights,
            mock_retrieve_memory,
            mock_load_context,  
            mock_get_action_cost,
    ):
        success_result = SimulationResult(
            action=RecoveryAction.RETRY_PAYMENT,
            outcome=SimulationOutcome.SUCCESS,
            is_payment_attempt=True,
            is_provider_execution=True,
            provider_reference="sim_retry_payment_payment_001_1",
        )

        policy_decision = PolicyDecision(
            approved=True,
            action="RETRY_PAYMENT",
            expected_net_recovery=20.0,
            reasons=["Expected net recovery is positive"],
        )

        with patch(
            "app.services.recovery_pipeline.run_recovery_pipeline",
            return_value=(policy_decision, success_result),
        ) as mock_pipeline:

            result_policy, result_simulation = run_recovery_until_resolved(
                db=self.db,
                recovery_case=self.recovery_case,
                llm_decision_service=self.llm_decision_service,
                policy_engine=self.policy_engine,
                payment_provider=self.payment_provider,
            )

        self.assertIs(result_policy, policy_decision)
        self.assertIs(result_simulation, success_result)

        mock_pipeline.assert_called_once()

    def test_policy_rejection_stops_recovery_cycle(
            self,
            mock_ground_truth_probability,
            mock_expected_net_recovery,
            mock_build_historical_insights,
            mock_retrieve_memory,
            mock_load_context,  
            mock_get_action_cost,
            ):
        rejected_policy = PolicyDecision(
            approved=False,
            action="RETRY_PAYMENT",
            expected_net_recovery=0.0,
            reasons=[
                "Expected net recovery must be positive."
            ],
        )

        with patch(
            "app.services.recovery_pipeline.run_recovery_pipeline",
            return_value=(rejected_policy, None),
        ) as mock_pipeline:

            result_policy, result_simulation = run_recovery_until_resolved(
                db=self.db,
                recovery_case=self.recovery_case,
                llm_decision_service=self.llm_decision_service,
                policy_engine=self.policy_engine,
                payment_provider=self.payment_provider,
            )

        self.assertIs(result_policy, rejected_policy)
        self.assertIsNone(result_simulation)

        mock_pipeline.assert_called_once()

    def test_stop_or_escalate_does_not_trigger_next_cycle(
            self,
            mock_ground_truth_probability,
            mock_expected_net_recovery,
            mock_build_historical_insights,
            mock_retrieve_memory,
            mock_load_context,  
            mock_get_action_cost,
            ):
        stop_result = SimulationResult(
            action=RecoveryAction.STOP,
            outcome=SimulationOutcome.NOT_EXECUTED,
            is_payment_attempt=False,
            is_provider_execution=False,
            provider_reference=None,
        )

        policy_decision = PolicyDecision(
            approved=True,
            action="STOP",
            expected_net_recovery=0.0,
            reasons=["No economically viable recovery action remains."],
        )

        with patch(
            "app.services.recovery_pipeline.run_recovery_pipeline",
            return_value=(policy_decision, stop_result),
        ) as mock_pipeline:

            result_policy, result_simulation = run_recovery_until_resolved(
                db=self.db,
                recovery_case=self.recovery_case,
                llm_decision_service=self.llm_decision_service,
                policy_engine=self.policy_engine,
                payment_provider=self.payment_provider,
            )

        self.assertIs(result_policy, policy_decision)
        self.assertIs(result_simulation, stop_result)

        mock_pipeline.assert_called_once()  

    def test_failed_recovery_stops_when_next_cycle_is_rejected(
            self,
            mock_ground_truth_probability,
            mock_expected_net_recovery,
            mock_build_historical_insights,
            mock_retrieve_memory,
            mock_load_context,  
            mock_get_action_cost,
            ):
        failed_result = SimulationResult(
            action=RecoveryAction.RETRY_PAYMENT,
            outcome=SimulationOutcome.FAILED,
            is_payment_attempt=True,
            is_provider_execution=True,
            provider_reference="sim_retry_payment_payment_001_1",
        )

        first_policy = PolicyDecision(
            approved=True,
            action="RETRY_PAYMENT",
            expected_net_recovery=20.0,
            reasons=["Expected net recovery is positive"],
        )

        rejected_policy = PolicyDecision(
            approved=False,
            action="SEND_PAYMENT_LINK",
            expected_net_recovery=0.0,
            reasons=["Cooldown period is still active."],
        )

        with patch(
            "app.services.recovery_pipeline.run_recovery_pipeline",
            side_effect=[
                (first_policy, failed_result),
                (rejected_policy, None),
            ],
        ) as mock_pipeline:

            policy_decision, simulation_result = run_recovery_until_resolved(
                db=self.db,
                recovery_case=self.recovery_case,
                llm_decision_service=self.llm_decision_service,
                policy_engine=self.policy_engine,
                payment_provider=self.payment_provider,
            )

        self.assertIs(policy_decision, rejected_policy)
        self.assertIsNone(simulation_result)

        self.assertEqual(mock_pipeline.call_count, 2) 

if __name__ == "__main__":
    unittest.main()