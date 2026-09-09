"""Command-line entry point for OpsGuard."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agents import build_provider
from .io import load_json, write_json
from .workflow import process_case


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Process an EzyHelpers operations case.")
    parser.add_argument("--case", default="data/synthetic_no_show_case.json")
    parser.add_argument("--bookings", default="data/bookings.json")
    parser.add_argument("--helpers", default="data/helpers.json")
    parser.add_argument("--policies", default="data/policies.json")
    parser.add_argument("--mode", choices=["mock", "openai"], default="mock")
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--output", default="outputs/demo_result.json")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    root = Path.cwd()
    case = load_json(root / args.case)
    bookings = load_json(root / args.bookings)
    helpers = load_json(root / args.helpers)
    policies = load_json(root / args.policies)
    agent = build_provider(args.mode, args.model)
    result = process_case(case, bookings, helpers, policies, agent)
    write_json(root / args.output, result)

    summary = {
        "case_id": result["case_id"],
        "status": result["status"],
        "priority": result.get("operational_facts", {}).get("priority"),
        "case_type": result.get("agent_intake", {}).get("case_type"),
        "recommended_helper": (result.get("recommended_replacement") or {}).get("name"),
        "approval_required": result.get("approval_control", {}).get("approval_required"),
        "output": str(root / args.output),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

