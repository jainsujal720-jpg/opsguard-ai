"""Run the synthetic case with a live OpenAI model without saving the API key.

The script first checks OPENAI_API_KEY. If it is not configured, it asks for
the key using hidden terminal input and keeps it only in this Python process.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from opsguard.agents import build_provider  # noqa: E402
from opsguard.io import load_json, write_json  # noqa: E402
from opsguard.workflow import process_case  # noqa: E402


def obtain_api_key() -> str:
    """Return a configured key or request one without displaying or saving it."""
    configured = os.environ.get("OPENAI_API_KEY", "").strip()
    if configured:
        return configured

    print("No OPENAI_API_KEY environment variable was found.")
    print("Paste the API key at the hidden prompt. It will not be displayed or saved.")
    entered = getpass.getpass("OpenAI API key: ").strip()
    if not entered:
        raise RuntimeError("No API key was entered; the live demonstration was not run.")
    return entered


def main() -> None:
    parser = argparse.ArgumentParser(description="Run OpsGuard using a live OpenAI model.")
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument(
        "--output",
        default=str(PROJECT_ROOT / "outputs" / "live_result.json"),
    )
    args = parser.parse_args()

    # This assignment exists only until the Python process ends. The key is not
    # written to a file, printed, included in output JSON, or added to logs.
    os.environ["OPENAI_API_KEY"] = obtain_api_key()

    case = load_json(PROJECT_ROOT / "data" / "synthetic_no_show_case.json")
    bookings = load_json(PROJECT_ROOT / "data" / "bookings.json")
    helpers = load_json(PROJECT_ROOT / "data" / "helpers.json")
    policies = load_json(PROJECT_ROOT / "data" / "policies.json")
    provider = build_provider("openai", model=args.model)

    print(f"Calling {args.model} through the OpenAI Responses API...")
    result = process_case(case, bookings, helpers, policies, provider)
    write_json(args.output, result)

    safe_summary = {
        "case_id": result["case_id"],
        "status": result["status"],
        "agent_provider": result["agent_provider"],
        "case_type": result["agent_intake"]["case_type"],
        "priority": result["operational_facts"]["priority"],
        "recommended_helper": (result.get("recommended_replacement") or {}).get("name"),
        "approval_required": result["approval_control"]["approval_required"],
        "output_file": str(Path(args.output).resolve()),
    }
    print("Live demonstration completed successfully:")
    print(json.dumps(safe_summary, indent=2))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nLive demonstration cancelled.", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(f"Live demonstration failed safely: {exc}", file=sys.stderr)
        raise SystemExit(1)

