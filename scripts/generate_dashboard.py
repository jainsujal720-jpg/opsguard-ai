"""Generate a readable single-case status dashboard from an OpsGuard result."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def escape(value) -> str:
    return html.escape(str(value))


def cards(items: list[dict], title_key: str, detail_key: str | None = None) -> str:
    rendered = []
    for item in items:
        detail = f"<small>{escape(item.get(detail_key, ''))}</small>" if detail_key else ""
        rendered.append(f"<li><span>{escape(item.get(title_key, ''))}</span>{detail}</li>")
    return "".join(rendered) or "<li><span>None</span></li>"


def render(result: dict) -> str:
    progress = result["workflow_progress"]
    replacement = result.get("recommended_replacement") or {}
    approval = result["approval_control"]
    message = result.get("customer_messages", {}).get("progress_update", "No draft available.")
    manager = result.get("manager_approval_request") or {}
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>OpsGuard Case {escape(result['case_id'])}</title>
<style>
body{{margin:0;background:#f4f6f8;color:#182230;font:16px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
main{{max-width:1050px;margin:40px auto;padding:0 22px}}h1{{margin-bottom:4px}}.sub{{color:#667085}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px;margin:24px 0}}
.card{{background:white;border:1px solid #e4e7ec;border-radius:14px;padding:20px;box-shadow:0 3px 12px #1018280d}}
.metric{{font-size:26px;font-weight:700;margin-top:8px}}.high{{color:#b42318}}.waiting{{color:#b54708}}
.cols{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}ul{{list-style:none;padding:0;margin:0}}
li{{border-bottom:1px solid #eaecf0;padding:12px 0}}li:last-child{{border-bottom:0}}small{{display:block;color:#667085;margin-top:4px}}
.done li:before{{content:"✓";color:#067647;font-weight:700;margin-right:10px}}.pending li:before{{content:"○";color:#b54708;font-weight:700;margin-right:10px}}
.notdone li:before{{content:"—";color:#667085;font-weight:700;margin-right:10px}}blockquote{{margin:0;padding:16px;border-left:4px solid #175cd3;background:#eff8ff;border-radius:8px}}
.badge{{display:inline-block;padding:6px 10px;border-radius:999px;background:#fff4e5;color:#b54708;font-weight:650}}
@media(max-width:720px){{.cols{{grid-template-columns:1fr}}}}
</style></head>
<body><main>
<h1>OpsGuard Operations Case</h1><div class="sub">A transparent view of what is complete, waiting, and not executed</div>
<div class="grid">
<div class="card"><div>Case</div><div class="metric">{escape(result['case_id'])}</div></div>
<div class="card"><div>Priority</div><div class="metric high">{escape(result['operational_facts']['priority'].title())}</div></div>
<div class="card"><div>Recommended helper</div><div class="metric">{escape(replacement.get('name', 'None'))}</div></div>
<div class="card"><div>Case status</div><div class="metric waiting">Waiting</div><small>{escape(result['status'].replace('_', ' '))}</small></div>
</div>
<div class="cols">
<section class="card done"><h2>Completed</h2><ul>{cards(progress['completed'], 'label')}</ul></section>
<section class="card pending"><h2>Waiting</h2><ul>{cards(progress['waiting'], 'label')}</ul></section>
</div>
<section class="card notdone" style="margin-top:18px"><h2>Not executed</h2><ul>{cards(progress['not_executed'], 'label', 'reason')}</ul></section>
<section class="card" style="margin-top:18px"><h2>Customer message draft</h2><blockquote>{escape(message)}</blockquote><p><span class="badge">Draft only — not sent</span></p></section>
<section class="card" style="margin-top:18px"><h2>Manager decision</h2><p><strong>{escape(manager.get('decision', 'No approval needed'))}</strong></p><p>{escape(manager.get('case_summary', ''))}</p><p>{escape(manager.get('replacement_summary', ''))}</p><p><span class="badge">No refund issued</span></p></section>
<section class="card" style="margin-top:18px"><h2>Next action</h2><p>{escape(progress['next_action'])}</p></section>
</main></body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(PROJECT_ROOT / "outputs" / "demo_result.json"))
    parser.add_argument("--output", default=str(PROJECT_ROOT / "outputs" / "case_dashboard.html"))
    args = parser.parse_args()
    result = json.loads(Path(args.input).read_text(encoding="utf-8"))
    Path(args.output).write_text(render(result), encoding="utf-8")
    print(f"Dashboard created: {Path(args.output).resolve()}")


if __name__ == "__main__":
    main()
