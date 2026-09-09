"""Wrap an OpsGuard result in a synthetic n8n email-test payload."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare the n8n synthetic email payload.")
    parser.add_argument("--email", required=True, help="Your verified test inbox address")
    parser.add_argument(
        "--result",
        default=str(PROJECT_ROOT / "outputs" / "live_result.json"),
        help="A current OpsGuard result JSON file",
    )
    parser.add_argument(
        "--output",
        default=str(PROJECT_ROOT / "outputs" / "n8n_email_test_payload.json"),
    )
    args = parser.parse_args()
    result = json.loads(Path(args.result).read_text(encoding="utf-8"))
    payload = {
        "test_mode": True,
        "test_customer_email": args.email.strip(),
        "test_manager_email": args.email.strip(),
        "case_result": result,
    }
    Path(args.output).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Synthetic email payload created: {Path(args.output).resolve()}")
    print("Both customer and manager messages will go to the same test inbox.")


if __name__ == "__main__":
    main()

