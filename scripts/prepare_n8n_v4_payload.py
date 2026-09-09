"""Create a synthetic OpsGuard V4 case payload for n8n."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def normalize_phone(value: str) -> str:
    phone = re.sub(r"[\s()-]", "", value.strip())
    phone = re.sub(r"^whatsapp:", "", phone, flags=re.IGNORECASE)
    if not re.fullmatch(r"\+[1-9]\d{7,14}", phone):
        raise ValueError("Worker phone must be E.164, for example +919876543210")
    return phone


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare the synthetic n8n V4 payload.")
    parser.add_argument("--email", required=True, help="Test inbox used for customer and manager messages")
    parser.add_argument("--worker-phone", required=True, help="Sandbox-linked WhatsApp number in E.164 format")
    parser.add_argument(
        "--result",
        default=str(PROJECT_ROOT / "outputs" / "demo_result.json"),
        help="A current OpsGuard result JSON file",
    )
    parser.add_argument(
        "--output",
        default=str(PROJECT_ROOT / "outputs" / "n8n_v4_test_payload.json"),
    )
    args = parser.parse_args()

    result = json.loads(Path(args.result).read_text(encoding="utf-8"))
    payload = {
        "test_mode": True,
        "test_customer_email": args.email.strip(),
        "test_manager_email": args.email.strip(),
        "test_worker_phone": normalize_phone(args.worker_phone),
        "case_result": result,
    }
    output = Path(args.output)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Synthetic V4 payload created: {output.resolve()}")
    print("No real helper assignment or refund will be executed.")


if __name__ == "__main__":
    main()
