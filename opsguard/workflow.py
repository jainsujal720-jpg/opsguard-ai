"""End-to-end governed workflow orchestration."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .agents import AgentProvider
from .formatting import friendly_time, inr
from .rules import (
    calculate_operational_facts,
    choose_replacement,
    determine_approval,
    find_eligible_helpers,
    validate_booking,
    validate_recommendation,
)


def retrieve_policy(case_type: str, policies: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next((policy for policy in policies if case_type in policy["applies_to"]), None)


def audit_event(step: str, status: str, detail: str) -> dict[str, str]:
    return {
        "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
        "step": step,
        "status": status,
        "detail": detail,
    }


def build_progress_view(
    approval: dict[str, Any],
    replacement: dict[str, Any] | None,
) -> dict[str, Any]:
    """Explain what has happened and what has not yet happened."""
    completed = [
        {"step": "case_received", "label": "Customer case received"},
        {"step": "booking_validated", "label": "Booking and check-in verified"},
        {"step": "priority_calculated", "label": "Operational priority calculated"},
        {"step": "message_classified", "label": "Customer message classified by AI"},
        {"step": "policy_matched", "label": "Relevant no-show policy matched"},
        {"step": "replacement_checked", "label": "Replacement candidates checked"},
    ]
    waiting = []
    if replacement:
        waiting.append(
            {
                "step": "replacement_acceptance",
                "label": f"Waiting to contact {replacement['name']} and receive acceptance",
            }
        )
    if approval["approval_required"]:
        waiting.append(
            {
                "step": "refund_approval",
                "label": f"Waiting for manager decision on {inr(approval['requested_refund_inr'])} refund",
            }
        )

    not_executed = [
        {
            "action": "helper_contact",
            "label": "No real helper has been contacted",
            "reason": "The n8n communication workflow has not been triggered.",
        },
        {
            "action": "customer_message",
            "label": "No customer message has been sent",
            "reason": "The message is a reviewed draft only.",
        },
        {
            "action": "refund",
            "label": "No refund has been issued",
            "reason": "The synthetic refund is waiting for manager approval.",
        },
    ]
    return {
        "completed": completed,
        "waiting": waiting,
        "not_executed": not_executed,
        "next_action": (
            "Trigger the synthetic n8n communication workflow and collect the manager's refund decision."
        ),
    }


def build_manager_approval_request(
    case: dict[str, Any],
    facts: dict[str, Any],
    replacement: dict[str, Any] | None,
    approval: dict[str, Any],
) -> dict[str, Any] | None:
    """Create a concise review packet without performing the decision."""
    if not approval["approval_required"]:
        return None
    replacement_text = (
        f"{replacement['name']} is eligible and could arrive around "
        f"{friendly_time(replacement['estimated_arrival'])}."
        if replacement
        else "No eligible replacement was found."
    )
    return {
        "title": f"Refund approval required — case {case['case_id']}",
        "decision": f"Approve or decline the requested {inr(approval['requested_refund_inr'])} refund.",
        "case_summary": (
            f"The confirmed cleaner had not checked in and was {facts['minutes_late']} minutes late. "
            f"The customer had {facts['hours_to_customer_deadline']} hours remaining before the stated deadline."
        ),
        "replacement_summary": replacement_text,
        "policy_limit": inr(approval["automatic_refund_limit_inr"]),
        "approve_effect": "The synthetic workflow may proceed to the refund-confirmation step.",
        "decline_effect": "The refund remains unissued and the customer receives a reviewed decline/update message.",
        "executed": False,
    }


def process_case(
    case: dict[str, Any],
    bookings: list[dict[str, Any]],
    helpers: list[dict[str, Any]],
    policies: list[dict[str, Any]],
    agent: AgentProvider,
) -> dict[str, Any]:
    audit: list[dict[str, str]] = [
        audit_event("case_received", "completed", f"Received case {case['case_id']}.")
    ]

    booking_validation = validate_booking(case, bookings)
    audit.append(
        audit_event(
            "booking_validation",
            "completed" if booking_validation["valid"] else "blocked",
            booking_validation["reason"],
        )
    )
    if not booking_validation["valid"]:
        return {
            "case_id": case["case_id"],
            "status": "blocked",
            "booking_validation": booking_validation,
            "audit_log": audit,
        }

    booking = booking_validation["booking"]
    facts = calculate_operational_facts(case, booking)
    audit.append(audit_event("fact_calculation", "completed", facts["priority_reason"]))

    intake = agent.analyze_message(case["customer_message"])
    audit.append(
        audit_event(
            "agent_intake",
            "completed",
            f"{agent.name} classified the case as {intake['case_type']}.",
        )
    )

    policy = retrieve_policy(intake["case_type"], policies)
    audit.append(
        audit_event(
            "policy_retrieval",
            "completed" if policy else "review_required",
            policy["policy_id"] if policy else "No matching policy found.",
        )
    )

    candidates = find_eligible_helpers(case, booking, helpers)
    replacement = choose_replacement(candidates)
    recommendation_validation = validate_recommendation(replacement, candidates)
    audit.append(
        audit_event(
            "replacement_validation",
            "completed" if recommendation_validation["valid"] else "escalated",
            recommendation_validation["reason"],
        )
    )

    approval = determine_approval(case)
    audit.append(
        audit_event(
            "approval_control",
            "waiting_for_approval" if approval["approval_required"] else "automatic",
            approval["approval_reason"],
        )
    )

    automatic_actions: list[dict[str, Any]] = []
    approval_actions: list[dict[str, Any]] = []
    customer_messages: dict[str, str] = {}
    if recommendation_validation["valid"] and replacement:
        arrival_time = friendly_time(replacement["estimated_arrival"])
        customer_messages["progress_update"] = (
            f"Hi {case['customer_name']}, we're sorry that your scheduled helper did not arrive. "
            f"We have identified an eligible replacement who could arrive around {arrival_time}. "
            "We are contacting the helper and will confirm the assignment once accepted. "
            f"Your {inr(approval['requested_refund_inr'])} refund request is being reviewed by our operations manager."
        )
        automatic_actions.extend(
            [
                {
                    "action": "contact_replacement_helper",
                    "helper_id": replacement["helper_id"],
                    "status": "prepared_for_n8n",
                    "executed": False,
                },
                {
                    "action": "send_customer_progress_update",
                    "status": "draft_prepared_not_sent",
                    "executed": False,
                    "draft": customer_messages["progress_update"],
                },
            ]
        )
    else:
        automatic_actions.append(
            {
                "action": "escalate_to_operations_manager",
                "status": "prepared_for_n8n",
                "executed": False,
            }
        )

    refund_action = {
        "action": "issue_refund",
        "amount_inr": approval["requested_refund_inr"],
        "status": "waiting_for_manager" if approval["approval_required"] else "prepared_for_n8n",
        "executed": False,
    }
    if approval["approval_required"]:
        approval_actions.append(refund_action)
    elif approval["requested_refund_inr"] > 0:
        automatic_actions.append(refund_action)

    final_status = "waiting_for_manager_approval" if approval_actions else "ready_for_automation"
    progress = build_progress_view(approval, replacement)
    manager_request = build_manager_approval_request(case, facts, replacement, approval)
    audit.append(audit_event("case_orchestration", "completed", f"Case is {final_status}."))

    return {
        "case_id": case["case_id"],
        "status": final_status,
        "agent_provider": agent.name,
        "booking_validation": {
            "valid": booking_validation["valid"],
            "reason": booking_validation["reason"],
        },
        "operational_facts": facts,
        "agent_intake": intake,
        "matched_policy": policy,
        "replacement_candidates": candidates,
        "recommended_replacement": replacement,
        "recommendation_validation": recommendation_validation,
        "approval_control": approval,
        "customer_messages": customer_messages,
        "manager_approval_request": manager_request,
        "automatic_actions": automatic_actions,
        "approval_actions": approval_actions,
        "workflow_progress": progress,
        "audit_log": audit,
    }
