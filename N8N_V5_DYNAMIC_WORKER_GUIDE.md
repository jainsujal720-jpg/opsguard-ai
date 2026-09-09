# OpsGuard V5 — Simple Import and Test Guide

OpsGuard V5 upgrades the existing synthetic OpsGuard workflow with deterministic worker selection and automatic retry.

## What V5 does

- Reads workers from an n8n Data Table.
- Filters workers using availability, opt-in, service, area and distance rules.
- Ranks eligible workers using rating, acceptance rate, distance and workload.
- Sends the assignment request to the highest-ranked worker.
- Automatically sends the next offer when a worker declines.
- Confirms the customer only after a worker accepts.
- Escalates to operations when no candidate remains.
- Records actions in the existing `OpsGuard Audit` table.

This package is for synthetic testing. It does not create a real worker assignment, payment or refund.

## Files to use

1. `n8n/opsguard_dynamic_worker_workflow_v5.json` — import into n8n.
2. `data/opsguard_workers_sample.csv` — import as the worker table.
3. `data/opsguard_cases_template.csv` — import as the case-state table.

## Manual setup

### 1. Create the worker table

1. Open **Personal → Data tables** in n8n.
2. Click **Create data table**.
3. Choose **Import CSV**.
4. Upload `opsguard_workers_sample.csv`.
5. Name the table exactly `OpsGuard Workers`.

The phone numbers in this CSV are deliberately fictional. In `test_mode`, V5 sends every worker offer to the `test_worker_phone` supplied in the test request.

### 2. Create the case-state table

1. Create another Data Table using **Import CSV**.
2. Upload `opsguard_cases_template.csv`.
3. Name the table exactly `OpsGuard Cases`.

The `SETUP-ROW` can remain in the table; it is harmless.

### 3. Import the workflow

1. Open **Workflows** in n8n.
2. Choose **Import from file**.
3. Upload `opsguard_dynamic_worker_workflow_v5.json`.

### 4. Reconnect credentials and tables

1. Select your existing Gmail credential in every Gmail node showing a warning.
2. In both `Send First Worker Offer` and `Send Next Worker Offer`, select your existing Twilio credential.
3. In those two nodes, reuse the same three Twilio values that worked in V4:
   - Account SID in the URL
   - Twilio WhatsApp sandbox sender number
   - Worker-assignment Content SID
4. Open each Data Table node and select the named table shown in that node if n8n asks you to reconnect it.

Do not share your Twilio authentication token or place it in the workflow JSON.

### 5. Configure incoming WhatsApp replies

Activate/publish the workflow. In the Twilio WhatsApp sandbox custom inbound webhook, use:

`https://sujali.app.n8n.cloud/webhook/opsguard-v5-worker-reply`

Set the method to `POST` and save.

### 6. Start the synthetic test

Replace `YOUR_EMAIL` and `YOUR_TEST_WHATSAPP_NUMBER`, then run:

```bash
curl -X POST 'https://sujali.app.n8n.cloud/webhook/opsguard-v5-case-test' \
  -H 'Content-Type: application/json' \
  -d '{
    "test_mode": true,
    "test_customer_email": "YOUR_EMAIL",
    "test_manager_email": "YOUR_EMAIL",
    "test_worker_phone": "YOUR_TEST_WHATSAPP_NUMBER",
    "case_result": {
      "case_id": "V5-1001",
      "service_required": "Deep Cleaning",
      "service_area": "Indiranagar",
      "max_distance_km": 8,
      "approval_control": {
        "approval_required": true,
        "requested_refund_inr": 500
      },
      "customer_messages": {
        "progress_update": "Hi Priya, your scheduled helper did not arrive. We are checking available replacement workers now."
      },
      "manager_approval_request": {
        "decision": "Approve or decline the requested ₹500 refund.",
        "case_summary": "The confirmed helper is 30 minutes late and has not checked in.",
        "replacement_summary": "OpsGuard is dynamically ranking eligible replacement workers.",
        "policy_limit": "₹300"
      }
    }
  }'
```

Use the same WhatsApp number that joined your Twilio sandbox, including the country code, for example `+91...`.

## Expected test result

1. Anjali is selected first by the deterministic score.
2. Reply `R` or `DECLINE` to test automatic retry.
3. Meera should receive the next synthetic offer on the same sandbox test number.
4. Reply `C` or `ACCEPT`.
5. The customer receives the confirmation for Meera.
6. `OpsGuard Cases` shows the confirmed worker and final status.
7. `OpsGuard Audit` shows the first offer, decline, retry, acceptance and customer confirmation.

Use a new `case_id` for every full test, such as `V5-1002`.

## Deterministic score

The ranking formula is:

`rating × 20 + acceptance_rate × 20 − distance_km × 5 − current_workload × 10`

Opted-out, unavailable, wrong-service, wrong-area and over-distance workers are removed before scoring.
