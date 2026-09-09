from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from opsguard.agents import MockAgentProvider
from opsguard.formatting import friendly_time, inr
from opsguard.rules import validate_recommendation
from opsguard.workflow import process_case


ROOT = Path(__file__).resolve().parents[1]


def load(name: str):
    with (ROOT / "data" / name).open("r", encoding="utf-8") as handle:
        return json.load(handle)


class OpsGuardWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.case = load("synthetic_no_show_case.json")
        self.bookings = load("bookings.json")
        self.helpers = load("helpers.json")
        self.policies = load("policies.json")

    def run_case(self, case=None, helpers=None):
        return process_case(
            case or self.case,
            self.bookings,
            helpers or self.helpers,
            self.policies,
            MockAgentProvider(),
        )

    def test_synthetic_case_is_high_priority_no_show(self):
        result = self.run_case()
        self.assertEqual(result["agent_intake"]["case_type"], "helper_no_show")
        self.assertEqual(result["operational_facts"]["priority"], "high")
        self.assertEqual(result["operational_facts"]["minutes_late"], 30)

    def test_qualified_replacement_is_selected(self):
        result = self.run_case()
        self.assertEqual(result["recommended_replacement"]["name"], "Anjali")
        kavya = next(row for row in result["replacement_candidates"] if row["name"] == "Kavya")
        self.assertFalse(kavya["eligible"])
        self.assertIn("required_skill_missing", kavya["ineligibility_reasons"])

    def test_refund_requires_manager_approval(self):
        result = self.run_case()
        self.assertTrue(result["approval_control"]["approval_required"])
        self.assertEqual(result["status"], "waiting_for_manager_approval")
        self.assertEqual(result["approval_actions"][0]["amount_inr"], 500.0)

    def test_small_refund_can_follow_automatic_branch(self):
        case = copy.deepcopy(self.case)
        case["requested_refund_inr"] = 250
        result = self.run_case(case=case)
        self.assertFalse(result["approval_control"]["approval_required"])
        self.assertEqual(result["status"], "ready_for_automation")

    def test_ungrounded_recommendation_is_rejected(self):
        result = self.run_case()
        invented = copy.deepcopy(result["recommended_replacement"])
        invented["helper_id"] = "HLP-INVENTED"
        validation = validate_recommendation(invented, result["replacement_candidates"])
        self.assertFalse(validation["valid"])
        self.assertFalse(validation["checks"]["candidate_exists"])

    def test_no_eligible_replacement_escalates(self):
        helpers = copy.deepcopy(self.helpers)
        for helper in helpers:
            helper["available"] = False
        result = self.run_case(helpers=helpers)
        self.assertIsNone(result["recommended_replacement"])
        self.assertEqual(result["automatic_actions"][0]["action"], "escalate_to_operations_manager")

    def test_customer_message_uses_friendly_time(self):
        result = self.run_case()
        message = result["customer_messages"]["progress_update"]
        self.assertIn("10:15 AM", message)
        self.assertIn("₹500", message)
        self.assertNotIn("2026-09-08T10:15:00", message)

    def test_actions_are_clearly_marked_not_executed(self):
        result = self.run_case()
        all_actions = result["automatic_actions"] + result["approval_actions"]
        self.assertTrue(all(action["executed"] is False for action in all_actions))
        labels = [item["label"] for item in result["workflow_progress"]["not_executed"]]
        self.assertIn("No customer message has been sent", labels)
        self.assertIn("No refund has been issued", labels)

    def test_manager_receives_clear_approval_request(self):
        result = self.run_case()
        request = result["manager_approval_request"]
        self.assertIn("₹500", request["decision"])
        self.assertEqual(request["policy_limit"], "₹300")
        self.assertIn("10:15 AM", request["replacement_summary"])
        self.assertFalse(request["executed"])

    def test_friendly_formatters(self):
        self.assertEqual(friendly_time("2026-09-08T10:15:00+05:30"), "10:15 AM")
        self.assertEqual(inr(500), "₹500")


if __name__ == "__main__":
    unittest.main()
