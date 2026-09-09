# OpsGuard V4: Worker Assignment Setup

This guide adds a synthetic replacement-worker decision loop to OpsGuard. The worker can accept or decline in WhatsApp, the customer is notified only after acceptance, refund requests above the policy limit still require a manager decision, and each workflow action is written to an audit table.

No real worker assignment or refund is performed.

## What V4 adds

| Requirement | V4 behavior |
|---|---|
| Worker accepts or declines | WhatsApp quick-reply buttons feed a second n8n webhook |
| Customer receives a confirmed update | Gmail sends confirmation only on the accepted branch |
| Manager handles refunds above policy | Existing Gmail approve/decline step remains in the workflow |
| Every action is recorded | n8n Data Table upserts each state transition by idempotency key |

## 1. Import the workflow

Import `n8n/opsguard_worker_assignment_workflow_v4.json` into n8n.

The workflow has two triggers:

- **Receive Synthetic Case Result** starts the case, customer, refund, and assignment branches.
- **Receive Worker Reply** receives the worker's WhatsApp response asynchronously.

## 2. Create the audit table

In the same n8n project, open **Data tables**, create a table named exactly `OpsGuard Audit`, and add these string columns:

```text
idempotency_key
case_id
event_type
event_status
actor
worker_name
worker_phone
customer_email
manager_email
replacement_eta
message_sid
details
event_timestamp
```

n8n adds its own row ID and created/updated timestamps. Do not add secrets to the table.

## 3. Create the WhatsApp assignment template

In Twilio Content Template Builder, create a `twilio/quick-reply` template.

Suggested body:

```text
Hi {{1}}, a replacement home-cleaning assignment is available for case {{2}}.
Can you arrive by {{3}}? Please choose an option.
```

Add two quick replies:

| Button title | Button ID/payload |
|---|---|
| Accept assignment | `ACCEPT` |
| Decline assignment | `DECLINE` |

Use synthetic samples when Twilio asks for example values. For out-of-session production messages, submit the template for WhatsApp approval. During sandbox testing, keep the test worker's device joined to the sandbox.

## 4. Configure credentials and placeholders

Select the same test Gmail credential in all seven Gmail nodes. In **Send Worker Assignment**, select your Twilio API credential and replace only these placeholders:

| Placeholder | Value |
|---|---|
| `REPLACE_WITH_ACCOUNT_SID` | Account SID inside the full Twilio Messages API URL |
| `REPLACE_WITH_TWILIO_SANDBOX_NUMBER` | Sandbox sender digits after `whatsapp:+` |
| `REPLACE_WITH_WORKER_ASSIGNMENT_CONTENT_SID` | Content SID for the quick-reply template |

Do not replace the whole request URL with the Account SID. Do not paste an auth token into the workflow, URL, body, screenshots, or repository.

## 5. Configure the inbound reply webhook

Activate the workflow and open **Receive Worker Reply**. Copy its production webhook URL, which ends with:

```text
/webhook/opsguard-v4-worker-reply
```

In the Twilio WhatsApp sandbox settings, paste that URL into **When a message comes in**, select `HTTP POST`, and save.

For production, put a small verification service or API gateway before n8n and validate Twilio's `X-Twilio-Signature`. The synthetic n8n webhook in this project does not perform that verification.

## 6. Prepare the synthetic case payload

From the repository root, run:

```bash
python scripts/prepare_n8n_v4_payload.py \
  --email 'YOUR_TEST_EMAIL' \
  --worker-phone '+COUNTRYCODE_NUMBER'
```

The worker number must be the WhatsApp device that joined the sandbox. The script writes `outputs/n8n_v4_test_payload.json`.

## 7. Trigger the case

Activate the workflow, copy the production URL for **Receive Synthetic Case Result**, and run:

```bash
curl -X POST '<N8N_V4_CASE_WEBHOOK_URL>' \
  -H 'Content-Type: application/json' \
  --data-binary @outputs/n8n_v4_test_payload.json
```

Expected immediate results:

1. The customer test inbox receives the initial update.
2. The test worker receives the WhatsApp assignment with Accept and Decline buttons.
3. A refund above the policy limit creates a manager approval email.
4. The audit table receives the initial events.

## 8. Test acceptance

Tap **Accept assignment** in WhatsApp. Expected result:

1. Twilio posts `ButtonPayload=ACCEPT` to **Receive Worker Reply**.
2. n8n finds the newest pending assignment for that worker number.
3. The customer receives the confirmed replacement email.
4. The audit table contains `worker_assignment_reply=accepted` and `customer_replacement_update=sent`.

## 9. Test decline

Run the case again with a new case ID, then tap **Decline assignment**. Expected result:

1. The customer does not receive a false confirmation.
2. The manager/test operations inbox receives the decline escalation.
3. The audit table contains `worker_assignment_reply=declined` and `operations_escalation=sent`.

The parser also accepts typed `ACCEPT` or `DECLINE`. Any other reply is recorded as `unrecognized`.

## 10. Verify the audit trail

Filter `OpsGuard Audit` by `case_id`. A complete acceptance-path demonstration should include:

- `customer_initial_update`
- `assignment_requested`
- `worker_assignment_reply` with `accepted`
- `customer_replacement_update`
- `refund_decision` with `approved`, `declined`, or `automatic`

The workflow uses deterministic idempotency keys so rerunning the same event updates its row instead of silently creating a duplicate event.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Worker receives no WhatsApp | Sandbox membership expired | Send the current `join ...` phrase again from the worker device |
| HTTP node says invalid URL | Full URL was replaced by the Account SID | Restore the full Messages API URL and replace only the SID segment |
| `ContentSid` error | Wrong or missing template SID | Copy the quick-reply template's `HX...` Content SID |
| Message sends but reply does nothing | Twilio inbound webhook not configured or workflow inactive | Use the production reply webhook URL and activate V4 |
| Reply webhook runs but finds no row | Phone formats differ or assignment send failed | Use E.164 in the payload and inspect the `assignment_requested` audit row |
| Data Table node fails | Table/column mismatch | Use the exact table and column names in this guide |
| n8n reports success but phone sees nothing | API acceptance is not final delivery | Inspect Twilio message logs and final delivery status |

## Production boundary

Before real use, add authenticated intake, Twilio signature verification, worker identity checks, assignment locking, delivery callbacks, retries, timeout/escalation handling, least-privilege credentials, and a durable operations database. Keep payment execution separate from manager approval until the payment provider confirms the actual refund.
