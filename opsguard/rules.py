"""Deterministic operational rules for facts, eligibility, and approval."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


def parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def validate_booking(case: dict[str, Any], bookings: list[dict[str, Any]]) -> dict[str, Any]:
    booking = next((row for row in bookings if row["booking_id"] == case["booking_id"]), None)
    if not booking:
        return {"valid": False, "reason": "booking_not_found", "booking": None}
    if booking["customer_id"] != case["customer_id"]:
        return {"valid": False, "reason": "customer_booking_mismatch", "booking": booking}
    if booking["status"] != "confirmed":
        return {"valid": False, "reason": "booking_not_confirmed", "booking": booking}
    return {"valid": True, "reason": "confirmed_booking_found", "booking": booking}


def calculate_operational_facts(case: dict[str, Any], booking: dict[str, Any]) -> dict[str, Any]:
    received_at = parse_datetime(case["received_at"])
    scheduled_at = parse_datetime(booking["scheduled_start"])
    deadline_at = parse_datetime(case["customer_deadline"])
    minutes_late = max(0, int((received_at - scheduled_at).total_seconds() // 60))
    hours_to_deadline = max(0.0, (deadline_at - received_at).total_seconds() / 3600)
    checked_in = bool(booking.get("check_in_time"))

    if not checked_in and minutes_late >= 15 and hours_to_deadline <= 4:
        priority = "high"
        priority_reason = "Confirmed no-show exceeds 15 minutes and customer deadline is within 4 hours."
    elif not checked_in and minutes_late >= 15:
        priority = "medium"
        priority_reason = "Confirmed helper has not checked in and is at least 15 minutes late."
    else:
        priority = "low"
        priority_reason = "No high-risk timing condition was detected."

    return {
        "received_at": case["received_at"],
        "scheduled_start": booking["scheduled_start"],
        "minutes_late": minutes_late,
        "helper_checked_in": checked_in,
        "hours_to_customer_deadline": round(hours_to_deadline, 2),
        "priority": priority,
        "priority_reason": priority_reason,
    }


def find_eligible_helpers(
    case: dict[str, Any],
    booking: dict[str, Any],
    helpers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    received_at = parse_datetime(case["received_at"])
    candidates: list[dict[str, Any]] = []
    for helper in helpers:
        reasons: list[str] = []
        if booking["service_type"] not in helper["skills"]:
            reasons.append("required_skill_missing")
        if not helper["available"]:
            reasons.append("not_available")
        if helper["distance_km"] > case["max_replacement_distance_km"]:
            reasons.append("outside_distance_limit")
        if helper.get("active_booking_overlap"):
            reasons.append("schedule_conflict")

        travel_minutes = int(15 + helper["distance_km"] * 6)
        earliest_at = parse_datetime(helper["available_from"])
        estimated_arrival = max(received_at, earliest_at) + timedelta(minutes=travel_minutes)
        if estimated_arrival > parse_datetime(case["customer_deadline"]):
            reasons.append("cannot_arrive_before_deadline")

        candidates.append(
            {
                "helper_id": helper["helper_id"],
                "name": helper["name"],
                "rating": helper["rating"],
                "distance_km": helper["distance_km"],
                "estimated_arrival": estimated_arrival.isoformat(),
                "eligible": not reasons,
                "ineligibility_reasons": reasons,
            }
        )

    return sorted(
        candidates,
        key=lambda row: (
            not row["eligible"],
            row["estimated_arrival"],
            -row["rating"],
        ),
    )


def choose_replacement(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next((candidate for candidate in candidates if candidate["eligible"]), None)


def determine_approval(case: dict[str, Any]) -> dict[str, Any]:
    requested = float(case.get("requested_refund_inr", 0))
    threshold = float(case.get("automatic_refund_limit_inr", 0))
    return {
        "requested_refund_inr": requested,
        "automatic_refund_limit_inr": threshold,
        "approval_required": requested > threshold,
        "approval_reason": (
            f"Requested refund of INR {requested:.0f} exceeds the automatic limit of INR {threshold:.0f}."
            if requested > threshold
            else "Refund is within the configured automatic limit."
        ),
    }


def validate_recommendation(
    replacement: dict[str, Any] | None,
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    if not replacement:
        return {
            "valid": False,
            "checks": {"candidate_exists": False, "eligible": False, "grounded_in_source_data": False},
            "reason": "No eligible replacement was found; the case must be escalated.",
        }
    source = next(
        (candidate for candidate in candidates if candidate["helper_id"] == replacement["helper_id"]),
        None,
    )
    checks = {
        "candidate_exists": source is not None,
        "eligible": bool(source and source["eligible"]),
        "grounded_in_source_data": source == replacement,
    }
    valid = all(checks.values())
    return {
        "valid": valid,
        "checks": checks,
        "reason": "Recommendation passed deterministic validation." if valid else "Recommendation failed validation.",
    }

