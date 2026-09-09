"""Agent providers for synthetic and live OpenAI message understanding."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Any


INTAKE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "case_type": {
            "type": "string",
            "enum": [
                "helper_no_show",
                "helper_late",
                "service_quality",
                "payment_issue",
                "other",
            ],
        },
        "urgency_signal": {"type": "string", "enum": ["low", "medium", "high"]},
        "customer_sentiment": {
            "type": "string",
            "enum": ["calm", "concerned", "frustrated", "unknown"],
        },
        "requested_resolution": {"type": "string"},
        "extracted_deadline": {"type": ["string", "null"]},
        "summary": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": [
        "case_type",
        "urgency_signal",
        "customer_sentiment",
        "requested_resolution",
        "extracted_deadline",
        "summary",
        "confidence",
    ],
    "additionalProperties": False,
}


class AgentProvider(ABC):
    """Interface that keeps agent interpretation separate from business rules."""

    name = "abstract"

    @abstractmethod
    def analyze_message(self, message: str) -> dict[str, Any]:
        raise NotImplementedError


class MockAgentProvider(AgentProvider):
    """Deterministic local substitute used for repeatable tests and demonstrations."""

    name = "deterministic_mock"

    def analyze_message(self, message: str) -> dict[str, Any]:
        lower = message.lower()
        no_show_terms = ("hasn't arrived", "has not arrived", "didn't arrive", "no-show", "not arrived")
        late_terms = ("late", "delayed")

        if any(term in lower for term in no_show_terms):
            case_type = "helper_no_show"
            confidence = 0.97
        elif any(term in lower for term in late_terms):
            case_type = "helper_late"
            confidence = 0.88
        else:
            case_type = "other"
            confidence = 0.60

        urgency_signal = "high" if any(
            term in lower for term in ("immediately", "urgent", "guests", "today")
        ) else "medium"
        sentiment = "frustrated" if any(
            term in lower for term in ("hasn't", "has not", "immediately", "unacceptable")
        ) else "concerned"
        requested_resolution = (
            "immediate_replacement" if "replacement" in lower or "arrange someone" in lower else "support_contact"
        )
        time_match = re.search(r"\b(?:by|at)\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm))\b", lower)

        return {
            "case_type": case_type,
            "urgency_signal": urgency_signal,
            "customer_sentiment": sentiment,
            "requested_resolution": requested_resolution,
            "extracted_deadline": time_match.group(1).upper() if time_match else None,
            "summary": "Customer reports that the scheduled helper has not arrived and requests an urgent replacement.",
            "confidence": confidence,
        }


class OpenAIResponsesProvider(AgentProvider):
    """Minimal standard-library client for the OpenAI Responses API."""

    name = "openai_responses_api"

    def __init__(self, model: str = "gpt-5.6-luna") -> None:
        self.model = model
        self.api_key = os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not configured. Use --mode mock or configure the key securely."
            )

    def analyze_message(self, message: str) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "instructions": (
                "You are the intake agent for a household-service operations team. "
                "Extract only information supported by the customer message. Do not invent "
                "bookings, policies, people, amounts, or operational facts."
            ),
            "input": message,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "opsguard_case_intake",
                    "strict": True,
                    "schema": INTAKE_SCHEMA,
                }
            },
            "store": False,
        }
        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI API request failed with HTTP {exc.code}: {details}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"OpenAI API network request failed: {exc.reason}") from exc

        output_text = body.get("output_text")
        if not output_text:
            for item in body.get("output", []):
                for content in item.get("content", []):
                    if content.get("type") == "output_text":
                        output_text = content.get("text")
                        break
        if not output_text:
            raise RuntimeError("The OpenAI response did not contain output text.")
        return json.loads(output_text)


def build_provider(mode: str, model: str = "gpt-5.6-luna") -> AgentProvider:
    if mode == "mock":
        return MockAgentProvider()
    if mode == "openai":
        return OpenAIResponsesProvider(model=model)
    raise ValueError(f"Unsupported agent mode: {mode}")

