# n8n V3 Setup Guide

This guide configures the synthetic OpsGuard V3 workflow for Gmail, manager approval, and the Twilio WhatsApp sandbox. It does not assign a real worker, contact a real customer, or issue a refund.

## Import

Import `n8n/opsguard_multichannel_workflow_v3.json` into n8n.

The workflow contains:

- one webhook trigger;
- five Gmail nodes;
- two decision nodes;
- three outcome-recording nodes; and
- one non-blocking Twilio HTTP Request branch.

## Gmail setup

Open each Gmail node and select the same test credential:

1. **Send Initial Customer Update**
2. **Email Manager and Wait**
3. **Send Automatic Confirmation**
4. **Send Approval Confirmation**
5. **Send Decline Update**

Use only test inboxes during the synthetic demonstration.

## Twilio setup

Open **Send WhatsApp Trial Template** and configure:

| Field | Value |
|---|---|
| Authentication | Predefined Credential Type |
| Credential Type | Twilio API |
| Twilio API | Your test Twilio credential |
| Body Content Type | Form URL Encoded |
| To | `whatsapp:+<test-recipient>` |
| From | `whatsapp:+<sandbox-sender>` |
| ContentSid | Twilio trial or approved template SID |

The Account SID must also replace `REPLACE_WITH_ACCOUNT_SID` inside the Messages API URL.

Do not paste an auth token into the URL, body, workflow JSON, or screenshots.

## Join the sandbox

Before testing, link the recipient device to the Twilio WhatsApp sandbox. From that device, send the displayed `join ...` phrase to the displayed sandbox number. Sandbox membership can expire and may need to be renewed.

## Trigger the workflow

Activate the workflow or put its webhook into test-listening mode. Copy the correct webhook URL and send a synthetic payload:

```bash
curl -X POST '<N8N_WEBHOOK_URL>' \
  -H 'Content-Type: application/json' \
  -d '{
    "case_id": "EZH-1042",
    "customer_name": "Priya",
    "minutes_late": 30,
    "customer_deadline": "13:00",
    "replacement_name": "Anjali",
    "replacement_eta": "10:15",
    "replacement_eligible": true,
    "refund_requested": 500,
    "automatic_refund_limit": 300,
    "synthetic": true
  }'
```

## Expected approval-path result

1. The webhook accepts the payload.
2. Gmail sends the initial customer update.
3. The approval rule routes the ₹500 request to the manager because it exceeds the ₹300 limit.
4. The manager receives approve and decline controls.
5. n8n waits for a decision.
6. The selected branch sends the final customer email and records the outcome.
7. The independent Twilio branch attempts the sandbox template.

## Confirm delivery

An n8n node can finish successfully before the recipient sees the message. Confirm both layers:

- In n8n: inspect the HTTP response and capture the Twilio Message SID.
- In Twilio: inspect message logs and confirm the final delivery status.
- On the device: confirm the message arrived in WhatsApp.

## Troubleshooting

| Error | Likely cause | Fix |
|---|---|---|
| `Invalid URL` | Account SID replaced the entire URL | Restore the full Twilio Messages API URL and replace only its SID segment |
| `Authorization failed` | Wrong or stale credential | Re-select the credential and confirm the Account SID matches |
| Trial account parameter error | Unsupported free-form WhatsApp body | Use the trial Content SID and its required variables |
| `ContentSid Required` | Template field missing | Add the `ContentSid` form field |
| Node succeeds but no message arrives | Sandbox expired or delivery failed later | Rejoin the sandbox and inspect Twilio message logs |

## Safety boundary

- Keep all payloads synthetic.
- Use phone numbers and inboxes you control.
- Do not connect payment or assignment actions during testing.
- Keep the WhatsApp branch configured to continue on error.
- Remove secrets and personal data before sharing screenshots or workflow exports.

