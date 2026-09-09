# Detailed Project Walkthrough

## 1. What this prototype solves

EzyHelpers receives a WhatsApp complaint from Priya: her cleaner has not arrived, guests are coming at 1 PM, she needs an immediate replacement, and she requests a refund of INR 500.

The prototype converts that unstructured complaint into a governed operations case. It verifies facts, applies the operating rules, finds a replacement, separates safe automation from sensitive action, and produces an audit trail.

## 2. Synthetic source information

The demonstration uses four controlled data files:

- `synthetic_no_show_case.json`: Priya's complaint and requested outcome.
- `bookings.json`: proof that the booking was confirmed for 9:00 AM and that no check-in occurred.
- `helpers.json`: three possible replacements, including availability, skill, distance, rating, and schedule-conflict information.
- `policies.json`: the no-show process and refund-approval rule.

All people, identifiers, events, and policies are fictional.

## 3. Why the system has two types of intelligence

### Deterministic intelligence

The functions in `rules.py` calculate facts that should not depend on an LLM:

- booking validity;
- minutes late;
- hours remaining before the customer's deadline;
- operational priority;
- replacement eligibility;
- estimated arrival;
- refund-approval requirement; and
- whether a recommendation exists in source data.

This makes the most important decisions repeatable and testable.

### Agent interpretation

The providers in `agents.py` interpret the customer message:

- case type;
- urgency language;
- customer sentiment;
- requested resolution;
- stated deadline; and
- concise case summary.

`MockAgentProvider` is a deterministic test double. `OpenAIResponsesProvider` sends the message to the OpenAI Responses API and requires a strict JSON Schema response. Both providers return the same data shape, so the workflow does not change when the provider changes.

## 4. End-to-end execution

`process_case` in `workflow.py` performs the following sequence:

1. Records that the case was received.
2. Finds and validates the booking.
3. Calculates that the helper is 30 minutes late.
4. Calculates that only 3.5 hours remain before the customer's deadline.
5. Classifies the message as `helper_no_show`.
6. Retrieves policy `SOP-NOSHOW-001`.
7. Evaluates every potential replacement.
8. Selects Anjali, the earliest eligible candidate.
9. Validates that Anjali exists in the source data and is eligible.
10. Allows the system to prepare replacement contact and a customer progress message.
11. Holds the INR 500 refund for manager approval because the automatic limit is INR 300.
12. Produces the complete audit log and final case state.

## 5. Why each helper received that outcome

### Anjali

- Has the required home-cleaning skill.
- Is available.
- Is 2.5 km away.
- Has no conflicting booking.
- Can arrive before 1 PM.

Result: eligible and recommended.

### Meena

- Also eligible.
- Becomes available later and has a later estimated arrival than Anjali.

Result: eligible backup candidate.

### Kavya

- Is nearby and available.
- Does not have the required home-cleaning skill.

Result: rejected by deterministic eligibility logic. A high rating or short distance cannot override the missing skill.

## 6. Human-in-the-loop control

The system treats these actions differently:

- Contact an eligible replacement: safe to prepare automatically.
- Send a progress update: safe to prepare automatically.
- Issue INR 500 refund: requires manager approval.
- Recommend a helper absent from source data: blocked by validation.
- Proceed when no eligible helper exists: blocked and escalated.

This is the central governance feature: the model may propose, but the rules and approval system determine what can proceed.

## 7. n8n's role

The validated V3 workflow orchestrates channels and approval without duplicating the business rules:

1. A webhook receives an already-processed synthetic case result.
2. Gmail sends the initial customer update.
3. A rule branch checks whether manager approval is required.
4. The approval path sends an interactive manager email and waits for a decision.
5. Gmail sends either the approved or declined customer update.
6. The automatic path sends a confirmation when no manager decision is required.
7. A parallel Twilio HTTP request attempts the WhatsApp trial template.
8. Edit Fields nodes record the workflow outcome for inspection.

The WhatsApp node is configured to continue on error. A Twilio or template failure therefore cannot block the email and manager-decision path.

## 8. Verification performed

Ten automated tests cover:

- high-priority no-show classification;
- valid replacement selection;
- exclusion of an unqualified helper;
- manager approval for the INR 500 refund;
- automatic handling for an INR 250 refund;
- rejection of an invented helper recommendation;
- escalation when no helper is eligible;
- customer-friendly time and currency formatting;
- explicit `executed: false` safety markers; and
- a complete manager approval request.

The HTTP service was started locally and tested through both `/health` and `/process`. The V3 n8n workflow was then imported and executed in n8n Cloud. The observed synthetic run delivered the initial Gmail update, paused for the manager decision, processed approval, sent the final Gmail update, and delivered the Twilio WhatsApp trial template.

## 9. What is and is not proven

Proven in the local prototype:

- the code compiles;
- all automated tests pass;
- the full synthetic case runs successfully;
- the HTTP API returns the expected governed result; and
- the n8n workflow imports and executes successfully;
- both approval paths and the automatic branch are explicitly represented;
- Gmail delivery and manager interaction work in the test environment; and
- Twilio accepts and delivers the sandbox template message.

Not yet proven:

- a production OpenAI provider evaluation at representative volume;
- a custom approved OpsGuard WhatsApp template;
- dynamic selection of the replacement worker's phone number;
- real booking, CRM, worker, payment, or refund-system integration;
- delivery callbacks, retry policy, idempotency, and operational alerting; and
- production performance, security, or regulatory compliance.

## 10. Recommended next iteration

1. Replace the Twilio trial content with an approved OpsGuard worker-assignment template.
2. Retrieve the proposed worker and phone number from an authenticated operations API.
3. Capture worker accept or decline replies and update the assignment atomically.
4. Add delivery-status callbacks, retries, idempotency keys, and failure alerts.
5. Write decisions and message identifiers to a durable audit store.
6. Integrate the payment provider only after policy and manager approval.
7. Add an evaluation dataset of 30–50 varied support cases.
8. Test security, privacy, throughput, and recovery behavior before production use.
