import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import crypto from 'node:crypto';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '..');
const source = path.join(root, 'n8n', 'opsguard_multichannel_workflow_v3.json');
const target = path.join(root, 'n8n', 'opsguard_worker_assignment_workflow_v4.json');
const workflow = JSON.parse(fs.readFileSync(source, 'utf8'));

const id = () => crypto.randomUUID();
const node = (name, type, typeVersion, position, parameters, extra = {}) => ({
  parameters,
  id: id(),
  name,
  type,
  typeVersion,
  position,
  ...extra,
});

const auditSchema = [
  'idempotency_key', 'case_id', 'event_type', 'event_status', 'actor',
  'worker_name', 'worker_phone', 'customer_email', 'manager_email',
  'replacement_eta', 'message_sid', 'details', 'event_timestamp',
].map((name) => ({
  id: name,
  displayName: name,
  required: false,
  defaultMatch: name === 'idempotency_key',
  canBeUsedToMatch: true,
  display: true,
  type: 'string',
  removed: false,
}));

function auditNode(name, position, values) {
  return node(name, 'n8n-nodes-base.dataTable', 1.1, position, {
    operation: 'upsert',
    dataTableId: { __rl: true, value: 'OpsGuard Audit', mode: 'name' },
    matchType: 'allConditions',
    filters: {
      conditions: [{
        keyName: 'idempotency_key',
        condition: 'eq',
        keyValue: values.idempotency_key,
      }],
    },
    columns: {
      mappingMode: 'defineBelow',
      value: values,
      matchingColumns: ['idempotency_key'],
      schema: auditSchema,
      attemptToConvertTypes: false,
      convertFieldsToString: false,
    },
    options: {},
  });
}

const initial = "$('Receive Synthetic Case Result').item.json.body";
const caseResult = `${initial}.case_result`;
const inbound = "$('Normalize Worker Reply').item.json";

workflow.name = 'OpsGuard V4 - Worker Decision, Refund Approval and Audit';
workflow.versionId = id();
workflow.nodes = [];
workflow.connections = {};

workflow.nodes.push(node('V4 Setup Notes', 'n8n-nodes-base.stickyNote', 1, [-1180, -620], {
  content: '## OpsGuard V4 setup\n1. Create an n8n Data Table named **OpsGuard Audit** with the columns listed in the V4 guide.\n2. Select your Gmail credential in all Gmail nodes.\n3. Select your Twilio API credential in **Send Worker Assignment**.\n4. Replace the three `REPLACE_WITH_...` values in that HTTP node.\n5. Create a WhatsApp quick-reply template with **Accept assignment** (`ACCEPT`) and **Decline assignment** (`DECLINE`).\n6. Activate the workflow and point the Twilio sandbox inbound webhook to the production URL for **Receive Worker Reply**.\n\nSynthetic testing only. No real assignment or refund is executed.',
  height: 390,
  width: 560,
  color: 5,
}));

workflow.nodes.push(node('Receive Synthetic Case Result', 'n8n-nodes-base.webhook', 2, [-980, -80], {
  httpMethod: 'POST',
  path: 'opsguard-v4-case-test',
  responseMode: 'onReceived',
  options: {},
}, { webhookId: id() }));

workflow.nodes.push(node('Send Initial Customer Update', 'n8n-nodes-base.gmail', 2.1, [-720, -220], {
  sendTo: '={{ $json.body.test_customer_email }}',
  subject: '=OpsGuard TEST — We are working on case {{ $json.body.case_result.case_id }}',
  emailType: 'text',
  message: '=SYNTHETIC TEST — No real helper or refund is involved.\n\n{{ $json.body.case_result.customer_messages.progress_update }}\n\nWe are asking the replacement worker to accept or decline the assignment. You will receive a confirmed update only after the worker accepts.\n\nCase ID: {{ $json.body.case_result.case_id }}',
  options: { appendAttribution: false, senderName: 'OpsGuard AI Test' },
}));

workflow.nodes.push(auditNode('Audit Initial Customer Update', [-460, -220], {
  idempotency_key: `={{ ${caseResult}.case_id + ':customer_initial' }}`,
  case_id: `={{ ${caseResult}.case_id }}`,
  event_type: 'customer_initial_update',
  event_status: 'sent',
  actor: 'system',
  worker_name: `={{ ${caseResult}.recommended_replacement.name }}`,
  worker_phone: `={{ ${initial}.test_worker_phone }}`,
  customer_email: `={{ ${initial}.test_customer_email }}`,
  manager_email: `={{ ${initial}.test_manager_email }}`,
  replacement_eta: `={{ ${caseResult}.recommended_replacement.estimated_arrival }}`,
  message_sid: '',
  details: 'Synthetic initial customer update sent',
  event_timestamp: '={{ $now.toISO() }}',
}));

workflow.nodes.push(node('Manager Approval Required?', 'n8n-nodes-base.if', 2.2, [-180, -220], {
  conditions: {
    options: { caseSensitive: true, leftValue: '', typeValidation: 'strict' },
    conditions: [{
      id: id(),
      leftValue: `={{ ${caseResult}.approval_control.approval_required }}`,
      rightValue: true,
      operator: { type: 'boolean', operation: 'true', singleValue: true },
    }],
    combinator: 'and',
  },
  options: {},
}));

workflow.nodes.push(node('Email Manager and Wait', 'n8n-nodes-base.gmail', 2.1, [80, -360], {
  operation: 'sendAndWait',
  sendTo: `={{ ${initial}.test_manager_email }}`,
  subject: `=OpsGuard TEST — Refund decision for {{ ${caseResult}.case_id }}`,
  message: `=SYNTHETIC APPROVAL TEST — Clicking a button will not issue a real refund.\n\n{{ ${caseResult}.manager_approval_request.decision }}\n\n{{ ${caseResult}.manager_approval_request.case_summary }}\n\n{{ ${caseResult}.manager_approval_request.replacement_summary }}\n\nAutomatic policy limit: {{ ${caseResult}.manager_approval_request.policy_limit }}`,
  responseType: 'approval',
  approvalOptions: { values: { approvalType: 'double', approveLabel: 'Approve test refund', disapproveLabel: 'Decline test refund' } },
  options: { appendAttribution: false },
}, { webhookId: id() }));

workflow.nodes.push(node('Manager Approved?', 'n8n-nodes-base.if', 2.2, [340, -360], {
  conditions: {
    options: { caseSensitive: true, leftValue: '', typeValidation: 'strict' },
    conditions: [{
      id: id(), leftValue: '={{ $json.data.approved }}', rightValue: true,
      operator: { type: 'boolean', operation: 'true', singleValue: true },
    }],
    combinator: 'and',
  },
  options: {},
}));

workflow.nodes.push(node('Send Refund Approval Confirmation', 'n8n-nodes-base.gmail', 2.1, [600, -440], {
  sendTo: `={{ ${initial}.test_customer_email }}`,
  subject: `=OpsGuard TEST — Refund approved for {{ ${caseResult}.case_id }}`,
  emailType: 'text',
  message: `=SYNTHETIC TEST — No real refund has been issued.\n\nYour refund request for ₹{{ ${caseResult}.approval_control.requested_refund_inr }} has been approved.\n\nCase ID: {{ ${caseResult}.case_id }}`,
  options: { appendAttribution: false, senderName: 'OpsGuard AI Test' },
}));

workflow.nodes.push(node('Send Refund Decline Update', 'n8n-nodes-base.gmail', 2.1, [600, -280], {
  sendTo: `={{ ${initial}.test_customer_email }}`,
  subject: `=OpsGuard TEST — Refund decision for {{ ${caseResult}.case_id }}`,
  emailType: 'text',
  message: `=SYNTHETIC TEST — No real refund has been issued.\n\nYour refund request for ₹{{ ${caseResult}.approval_control.requested_refund_inr }} was reviewed and was not approved.\n\nCase ID: {{ ${caseResult}.case_id }}`,
  options: { appendAttribution: false, senderName: 'OpsGuard AI Test' },
}));

workflow.nodes.push(auditNode('Audit Refund Approved', [860, -440], {
  idempotency_key: `={{ ${caseResult}.case_id + ':refund_approved' }}`,
  case_id: `={{ ${caseResult}.case_id }}`, event_type: 'refund_decision', event_status: 'approved', actor: 'manager',
  worker_name: `={{ ${caseResult}.recommended_replacement.name }}`, worker_phone: `={{ ${initial}.test_worker_phone }}`,
  customer_email: `={{ ${initial}.test_customer_email }}`, manager_email: `={{ ${initial}.test_manager_email }}`,
  replacement_eta: `={{ ${caseResult}.recommended_replacement.estimated_arrival }}`, message_sid: '',
  details: `=Synthetic refund approved: ₹{{ ${caseResult}.approval_control.requested_refund_inr }}`,
  event_timestamp: '={{ $now.toISO() }}',
}));

workflow.nodes.push(auditNode('Audit Refund Declined', [860, -280], {
  idempotency_key: `={{ ${caseResult}.case_id + ':refund_declined' }}`,
  case_id: `={{ ${caseResult}.case_id }}`, event_type: 'refund_decision', event_status: 'declined', actor: 'manager',
  worker_name: `={{ ${caseResult}.recommended_replacement.name }}`, worker_phone: `={{ ${initial}.test_worker_phone }}`,
  customer_email: `={{ ${initial}.test_customer_email }}`, manager_email: `={{ ${initial}.test_manager_email }}`,
  replacement_eta: `={{ ${caseResult}.recommended_replacement.estimated_arrival }}`, message_sid: '',
  details: `=Synthetic refund declined: ₹{{ ${caseResult}.approval_control.requested_refund_inr }}`,
  event_timestamp: '={{ $now.toISO() }}',
}));

workflow.nodes.push(node('Send Automatic Refund Update', 'n8n-nodes-base.gmail', 2.1, [80, -80], {
  sendTo: `={{ ${initial}.test_customer_email }}`,
  subject: `=OpsGuard TEST — Case processed for {{ ${caseResult}.case_id }}`,
  emailType: 'text',
  message: `=SYNTHETIC TEST — No real refund has been issued.\n\nThe refund request was within the automatic policy limit and did not require manager approval.\n\nCase ID: {{ ${caseResult}.case_id }}`,
  options: { appendAttribution: false, senderName: 'OpsGuard AI Test' },
}));

workflow.nodes.push(auditNode('Audit Automatic Refund', [340, -80], {
  idempotency_key: `={{ ${caseResult}.case_id + ':refund_automatic' }}`,
  case_id: `={{ ${caseResult}.case_id }}`, event_type: 'refund_decision', event_status: 'automatic', actor: 'policy_engine',
  worker_name: `={{ ${caseResult}.recommended_replacement.name }}`, worker_phone: `={{ ${initial}.test_worker_phone }}`,
  customer_email: `={{ ${initial}.test_customer_email }}`, manager_email: `={{ ${initial}.test_manager_email }}`,
  replacement_eta: `={{ ${caseResult}.recommended_replacement.estimated_arrival }}`, message_sid: '',
  details: 'Synthetic refund was within the automatic policy limit', event_timestamp: '={{ $now.toISO() }}',
}));

workflow.nodes.push(node('Send Worker Assignment', 'n8n-nodes-base.httpRequest', 4.2, [-720, 140], {
  method: 'POST',
  url: 'https://api.twilio.com/2010-04-01/Accounts/REPLACE_WITH_ACCOUNT_SID/Messages.json',
  authentication: 'predefinedCredentialType',
  nodeCredentialType: 'twilioApi',
  sendBody: true,
  contentType: 'form-urlencoded',
  bodyParameters: { parameters: [
    { name: 'To', value: `=whatsapp:{{ ${initial}.test_worker_phone }}` },
    { name: 'From', value: 'whatsapp:+REPLACE_WITH_TWILIO_SANDBOX_NUMBER' },
    { name: 'ContentSid', value: 'REPLACE_WITH_WORKER_ASSIGNMENT_CONTENT_SID' },
    { name: 'ContentVariables', value: `={{ JSON.stringify({'1': ${caseResult}.recommended_replacement.name, '2': ${caseResult}.case_id, '3': ${caseResult}.recommended_replacement.estimated_arrival}) }}` },
  ]},
  options: {},
}, { onError: 'continueRegularOutput' }));

workflow.nodes.push(auditNode('Audit Worker Assignment Request', [-460, 140], {
  idempotency_key: `={{ ${caseResult}.case_id + ':assignment_requested' }}`,
  case_id: `={{ ${caseResult}.case_id }}`, event_type: 'assignment_requested',
  event_status: "={{ $json.sid ? 'submitted_to_twilio' : 'send_failed' }}", actor: 'system',
  worker_name: `={{ ${caseResult}.recommended_replacement.name }}`, worker_phone: `={{ ${initial}.test_worker_phone }}`,
  customer_email: `={{ ${initial}.test_customer_email }}`, manager_email: `={{ ${initial}.test_manager_email }}`,
  replacement_eta: `={{ ${caseResult}.recommended_replacement.estimated_arrival }}`, message_sid: '={{ $json.sid || "" }}',
  details: 'Synthetic replacement assignment offered through WhatsApp', event_timestamp: '={{ $now.toISO() }}',
}));

workflow.nodes.push(node('Receive Worker Reply', 'n8n-nodes-base.webhook', 2, [-980, 520], {
  httpMethod: 'POST',
  path: 'opsguard-v4-worker-reply',
  responseMode: 'onReceived',
  options: {},
}, { webhookId: id() }));

workflow.nodes.push(node('Normalize Worker Reply', 'n8n-nodes-base.code', 2, [-720, 520], {
  jsCode: `const p = $json.body ?? $json;\nconst raw = String(p.ButtonPayload || p.ButtonText || p.Body || '').trim();\nconst normalized = raw.toUpperCase();\nlet decision = 'unrecognized';\nif (normalized === 'ACCEPT' || normalized.includes('ACCEPT ASSIGNMENT')) decision = 'accepted';\nif (normalized === 'DECLINE' || normalized.includes('DECLINE ASSIGNMENT')) decision = 'declined';\nconst workerPhone = String(p.From || '').replace(/^whatsapp:/i, '');\nreturn [{ json: { decision, raw_reply: raw, worker_phone: workerPhone, inbound_message_sid: p.MessageSid || p.SmsMessageSid || '', received_at: new Date().toISOString() } }];`,
}));

workflow.nodes.push(node('Find Pending Worker Assignment', 'n8n-nodes-base.dataTable', 1.1, [-460, 520], {
  operation: 'get',
  dataTableId: { __rl: true, value: 'OpsGuard Audit', mode: 'name' },
  matchType: 'allConditions',
  filters: { conditions: [
    { keyName: 'worker_phone', condition: 'eq', keyValue: `={{ ${inbound}.worker_phone }}` },
    { keyName: 'event_type', condition: 'eq', keyValue: 'assignment_requested' },
    { keyName: 'event_status', condition: 'eq', keyValue: 'submitted_to_twilio' },
  ]},
  returnAll: false,
  limit: 1,
  orderBy: true,
  orderByColumn: 'createdAt',
  orderByDirection: 'DESC',
}));

workflow.nodes.push(node('Worker Accepted?', 'n8n-nodes-base.if', 2.2, [-180, 520], {
  conditions: {
    options: { caseSensitive: true, leftValue: '', typeValidation: 'strict' },
    conditions: [{ id: id(), leftValue: `={{ ${inbound}.decision }}`, rightValue: 'accepted', operator: { type: 'string', operation: 'equals' } }],
    combinator: 'and',
  }, options: {},
}));

workflow.nodes.push(node('Worker Declined?', 'n8n-nodes-base.if', 2.2, [80, 660], {
  conditions: {
    options: { caseSensitive: true, leftValue: '', typeValidation: 'strict' },
    conditions: [{ id: id(), leftValue: `={{ ${inbound}.decision }}`, rightValue: 'declined', operator: { type: 'string', operation: 'equals' } }],
    combinator: 'and',
  }, options: {},
}));

workflow.nodes.push(auditNode('Audit Worker Accepted', [80, 420], {
  idempotency_key: `={{ $json.case_id + ':worker_accepted' }}`, case_id: '={{ $json.case_id }}',
  event_type: 'worker_assignment_reply', event_status: 'accepted', actor: 'replacement_worker',
  worker_name: '={{ $json.worker_name }}', worker_phone: '={{ $json.worker_phone }}', customer_email: '={{ $json.customer_email }}',
  manager_email: '={{ $json.manager_email }}', replacement_eta: '={{ $json.replacement_eta }}',
  message_sid: `={{ ${inbound}.inbound_message_sid }}`, details: `=Worker reply: {{ ${inbound}.raw_reply }}`,
  event_timestamp: `={{ ${inbound}.received_at }}`,
}));

workflow.nodes.push(node('Send Confirmed Replacement Update', 'n8n-nodes-base.gmail', 2.1, [340, 420], {
  sendTo: '={{ $json.customer_email }}',
  subject: '=OpsGuard TEST — Replacement confirmed for {{ $json.case_id }}',
  emailType: 'text',
  message: '=SYNTHETIC TEST — No real helper has been assigned.\n\nGood news — {{ $json.worker_name }} accepted the replacement assignment and is expected around {{ $json.replacement_eta }}.\n\nCase ID: {{ $json.case_id }}',
  options: { appendAttribution: false, senderName: 'OpsGuard AI Test' },
}));

workflow.nodes.push(auditNode('Audit Customer Replacement Confirmation', [600, 420], {
  idempotency_key: "={{ $('Audit Worker Accepted').item.json.case_id + ':customer_replacement_confirmed' }}",
  case_id: "={{ $('Audit Worker Accepted').item.json.case_id }}", event_type: 'customer_replacement_update', event_status: 'sent', actor: 'system',
  worker_name: "={{ $('Audit Worker Accepted').item.json.worker_name }}", worker_phone: "={{ $('Audit Worker Accepted').item.json.worker_phone }}",
  customer_email: "={{ $('Audit Worker Accepted').item.json.customer_email }}", manager_email: "={{ $('Audit Worker Accepted').item.json.manager_email }}",
  replacement_eta: "={{ $('Audit Worker Accepted').item.json.replacement_eta }}", message_sid: '',
  details: 'Synthetic customer notified after worker acceptance', event_timestamp: '={{ $now.toISO() }}',
}));

workflow.nodes.push(auditNode('Audit Worker Declined', [340, 660], {
  idempotency_key: `={{ $json.case_id + ':worker_declined' }}`, case_id: '={{ $json.case_id }}',
  event_type: 'worker_assignment_reply', event_status: 'declined', actor: 'replacement_worker',
  worker_name: '={{ $json.worker_name }}', worker_phone: '={{ $json.worker_phone }}', customer_email: '={{ $json.customer_email }}',
  manager_email: '={{ $json.manager_email }}', replacement_eta: '={{ $json.replacement_eta }}',
  message_sid: `={{ ${inbound}.inbound_message_sid }}`, details: `=Worker reply: {{ ${inbound}.raw_reply }}`,
  event_timestamp: `={{ ${inbound}.received_at }}`,
}));

workflow.nodes.push(node('Notify Operations of Worker Decline', 'n8n-nodes-base.gmail', 2.1, [600, 660], {
  sendTo: '={{ $json.manager_email }}',
  subject: '=OpsGuard TEST — Replacement declined for {{ $json.case_id }}',
  emailType: 'text',
  message: '=SYNTHETIC TEST — {{ $json.worker_name }} declined the replacement assignment for case {{ $json.case_id }}. Operations should select the next eligible worker. No customer confirmation was sent.',
  options: { appendAttribution: false, senderName: 'OpsGuard AI Test' },
}));

workflow.nodes.push(auditNode('Audit Operations Escalation', [860, 660], {
  idempotency_key: "={{ $('Audit Worker Declined').item.json.case_id + ':operations_escalated' }}",
  case_id: "={{ $('Audit Worker Declined').item.json.case_id }}", event_type: 'operations_escalation', event_status: 'sent', actor: 'system',
  worker_name: "={{ $('Audit Worker Declined').item.json.worker_name }}", worker_phone: "={{ $('Audit Worker Declined').item.json.worker_phone }}",
  customer_email: "={{ $('Audit Worker Declined').item.json.customer_email }}", manager_email: "={{ $('Audit Worker Declined').item.json.manager_email }}",
  replacement_eta: "={{ $('Audit Worker Declined').item.json.replacement_eta }}", message_sid: '',
  details: 'Operations notified to select another replacement', event_timestamp: '={{ $now.toISO() }}',
}));

workflow.nodes.push(auditNode('Audit Unrecognized Worker Reply', [340, 820], {
  idempotency_key: `={{ $json.case_id + ':worker_reply_unrecognized:' + ${inbound}.inbound_message_sid }}`,
  case_id: '={{ $json.case_id }}', event_type: 'worker_assignment_reply', event_status: 'unrecognized', actor: 'replacement_worker',
  worker_name: '={{ $json.worker_name }}', worker_phone: '={{ $json.worker_phone }}', customer_email: '={{ $json.customer_email }}',
  manager_email: '={{ $json.manager_email }}', replacement_eta: '={{ $json.replacement_eta }}',
  message_sid: `={{ ${inbound}.inbound_message_sid }}`, details: `=Unrecognized worker reply: {{ ${inbound}.raw_reply }}`,
  event_timestamp: `={{ ${inbound}.received_at }}`,
}));

const link = (from, to, output = 0) => {
  workflow.connections[from] ??= { main: [] };
  while (workflow.connections[from].main.length <= output) workflow.connections[from].main.push([]);
  workflow.connections[from].main[output].push({ node: to, type: 'main', index: 0 });
};

link('Receive Synthetic Case Result', 'Send Initial Customer Update');
link('Receive Synthetic Case Result', 'Send Worker Assignment');
link('Send Initial Customer Update', 'Audit Initial Customer Update');
link('Audit Initial Customer Update', 'Manager Approval Required?');
link('Manager Approval Required?', 'Email Manager and Wait', 0);
link('Manager Approval Required?', 'Send Automatic Refund Update', 1);
link('Email Manager and Wait', 'Manager Approved?');
link('Manager Approved?', 'Send Refund Approval Confirmation', 0);
link('Manager Approved?', 'Send Refund Decline Update', 1);
link('Send Refund Approval Confirmation', 'Audit Refund Approved');
link('Send Refund Decline Update', 'Audit Refund Declined');
link('Send Automatic Refund Update', 'Audit Automatic Refund');
link('Send Worker Assignment', 'Audit Worker Assignment Request');

link('Receive Worker Reply', 'Normalize Worker Reply');
link('Normalize Worker Reply', 'Find Pending Worker Assignment');
link('Find Pending Worker Assignment', 'Worker Accepted?');
link('Worker Accepted?', 'Audit Worker Accepted', 0);
link('Worker Accepted?', 'Worker Declined?', 1);
link('Audit Worker Accepted', 'Send Confirmed Replacement Update');
link('Send Confirmed Replacement Update', 'Audit Customer Replacement Confirmation');
link('Worker Declined?', 'Audit Worker Declined', 0);
link('Worker Declined?', 'Audit Unrecognized Worker Reply', 1);
link('Audit Worker Declined', 'Notify Operations of Worker Decline');
link('Notify Operations of Worker Decline', 'Audit Operations Escalation');

fs.writeFileSync(target, JSON.stringify(workflow, null, 2) + '\n');
console.log(`Created ${target}`);
