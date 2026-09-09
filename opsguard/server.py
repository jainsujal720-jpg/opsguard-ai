"""Small standard-library HTTP API that n8n can call."""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .agents import build_provider
from .io import load_json
from .workflow import process_case


class OpsGuardHandler(BaseHTTPRequestHandler):
    dependencies: dict[str, Any] = {}

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._send_json(200, {"status": "ok", "service": "opsguard"})
        else:
            self._send_json(404, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/process":
            self._send_json(404, {"error": "not_found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            case = json.loads(self.rfile.read(length).decode("utf-8"))
            result = process_case(case=case, **self.dependencies)
            self._send_json(200, result)
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            self._send_json(400, {"error": "invalid_case", "detail": str(exc)})
        except Exception as exc:  # demonstration server returns controlled JSON
            self._send_json(500, {"error": "processing_failed", "detail": str(exc)})

    def log_message(self, format: str, *args: Any) -> None:
        return


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the OpsGuard HTTP API.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--mode", choices=["mock", "openai"], default="mock")
    parser.add_argument("--model", default="gpt-5.6-luna")
    args = parser.parse_args()

    root = Path.cwd()
    OpsGuardHandler.dependencies = {
        "bookings": load_json(root / "data/bookings.json"),
        "helpers": load_json(root / "data/helpers.json"),
        "policies": load_json(root / "data/policies.json"),
        "agent": build_provider(args.mode, args.model),
    }
    server = ThreadingHTTPServer((args.host, args.port), OpsGuardHandler)
    print(f"OpsGuard listening on http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()

