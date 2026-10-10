# Dhaba Triage

FastAPI service for the Propel Dhaba take-home assignment. The first implementation is deliberately small: strict schemas, fixture classification, deterministic refund decisions, SQLite idempotency, and tests around the risky behavior.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
uvicorn dhaba_triage.app:app --app-dir src --reload
```

Then call:

```bash
curl -X POST http://127.0.0.1:8000/triage \
  -H "content-type: application/json" \
  --data @data/sample_ticket.json
```

To replay all attached tickets in fixture mode:

```bash
python scripts/run_fixture.py
```

## Design

`POST /triage` accepts one ticket in the attached JSON shape. The endpoint validates input with Pydantic, asks a classifier for non-money triage signals, passes trusted structured data to a deterministic refund policy, then stores the final response by ticket ID. Repeated ticket IDs return the stored decision and set `idempotency.replayed=true`.

The AI boundary is intentional: the classifier can suggest `category`, `severity`, `reply_draft`, `needs_human`, `confidence`, language, and prompt-injection detection. It cannot decide refund amount, select refundable purchases, or mark money actions as complete. Refund decisions come only from `refunds.py`.

The default classifier is fixture mode so evaluators can run the service without an API key. A real model can be added behind the same classifier interface, with strict output validation and fallback behavior preserved.

## API Contract

`POST /triage`

Request: one ticket matching the attached file shape:

- `id`
- `received_at`
- `subject`
- `body`
- `purchases[]` with `id`, `type`, `amount_inr`, `status`, `at`
- `app_opens_since_renewal`

Response:

- `ticket_id`
- `category`
- `severity`
- `refund`: `eligible`, `amount_inr`, `purchase_ids`, `reason_code`, `explanation`, `action`
- `reply_draft`
- `needs_human`
- `confidence`
- `classifier`: mode/model/low-confidence/validation-recovery/injection metadata
- `idempotency`: replay flag and stable decision ID

## Assumptions

- The attached JSON is the source of truth for the ticket schema.
- The PDF phrase "purchases are in one of four states: initiated, failed, successful, renewal" is interpreted as `status in initiated|failed|successful` and `type in trial|renewal`, because that is how the data is shaped.
- This service recommends refund actions; it does not call a payment provider.
- Fraud or unauthorized-use claims require human review and are never auto-refunded.
- A recent successful renewal with three or fewer app opens can be refund-eligible.
- Annual renewal with zero usage can be refund-eligible.
- Failed or initiated payments are not refundable because no successful captured payment is present.
- Raw subject/body text is not logged.

## Dashboard Metric

Track the percentage of tickets with `needs_human=true` split by reason: low confidence, prompt injection, manual refund review, or policy ambiguity. A sudden rise tells us the classifier, policy, or product flow needs attention.

## Results For The 12 Tickets

| Ticket | Category | Severity | Refund action | Amount | Human? | Confidence | Injection? | Do I agree? |
| --- | --- | --- | --- | ---: | --- | ---: | --- | --- |
| T-1001 | billing_refund | medium | recommend_refund | 249 | false | 0.82 | false | Yes. Recent trial conversion, zero usage. |
| T-1002 | technical_issue | high | none | 0 | false | 0.82 | false | Mostly. Could become human-review if crash volume spikes. |
| T-1003 | account_access | high | none | 0 | true | 0.60 | true | Yes. The refund instruction is prompt injection and ignored. |
| T-1004 | cancellation | medium | none | 0 | true | 0.45 | false | Yes. One-word cancellation is too ambiguous. |
| T-1005 | billing_activation_issue | medium | none | 0 | true | 0.78 | false | Yes. The renewal is only initiated, so solve activation/payment state, not refund. |
| T-1006 | billing_refund | high | recommend_refund | 1499 | false | 0.82 | false | Reasonable. Annual renewal with zero usage; policy could require human review in production. |
| T-1007 | feature_request | medium | none | 0 | false | 0.82 | false | Yes. Product feedback, not billing. |
| T-1008 | fraud_or_unauthorized | urgent | manual_review | 0 | true | 0.82 | false | Yes. Fraud claims must be manually verified. |
| T-1009 | billing_refund | medium | none | 0 | false | 0.82 | false | Yes. One failed and one successful payment is not a double successful charge. |
| T-1010 | invoice_request | medium | none | 0 | false | 0.82 | false | Yes. Generate/share invoice; no refund. |
| T-1011 | pre_sales_question | high | none | 0 | true | 0.60 | true | Yes. Prompt-injection attempt is ignored; answer product question only. |
| T-1012 | billing_refund | high | recommend_refund | 249 | false | 0.82 | false | Mostly. Recent renewal and low usage fit policy, despite angry tone. |

Ambiguous tickets: T-1004 has too little text; T-1005 needs payment-provider reconciliation; T-1006 depends on how strict annual-plan refund policy should be; T-1012 is emotionally charged but still policy-eligible. The system routes low-confidence and fraud/payment-activation ambiguity to humans.

Prompt-injection tickets: T-1003 and T-1011. The service records `classifier.prompt_injection_detected=true`, keeps `needs_human=true`, and does not follow the embedded instruction to reveal prompts, override refund policy, resolve the ticket, or refund all payments.

## Backend Track

At 50 tickets per second, I would split synchronous ingestion from model work:

- Accept the ticket, validate schema, create an idempotency record, and enqueue classification.
- Return a deterministic degraded response when the model path is slow or unavailable: `needs_human=true`, `category=unknown`, no refund action, and a safe reply draft.
- Cache/reuse classification results by ticket ID and classifier version.
- Rate-limit model calls and use a bounded worker pool so an outage does not exhaust the web process.

Storage sketch:

- `tickets(id, received_at, subject_hash, body_hash, app_opens_since_renewal, created_at)`
- `purchases(id, ticket_id, type, amount_inr, status, at)`
- `triage_decisions(decision_id, ticket_id, classifier_version, response_json, created_at)`
- `refund_actions(action_id, decision_id, purchase_id, amount_inr, status, created_at)`
- `model_events(event_id, ticket_id, classifier_version, outcome, latency_ms, redacted_error, created_at)`

For 3am debugging, I would add a per-ticket trace ID and a compact decision trace: classifier mode, confidence, validation attempts, refund rule matched, idempotency outcome, and latency. It should never include raw ticket body, GSTIN, company name, or payment identifiers in plain logs.

## AI Usage Notes

This version was built with Codex as a pair-programming agent. I directed the architecture, reviewed the assignment constraints, and checked the refund policy behavior against the attached tickets. Codex wrote most of the first-pass code and tests; I treated its output as draft implementation, then verified behavior with tests and the 12-ticket replay.

Best prompt used:

```text
I'm building a take-home assignment for a Full-Stack AI Engineer position.

Read the attached assignment PDF and dhaba_tickets.json carefully.

We will use Python, FastAPI, and Pydantic.

Before writing any code:

1. Analyse the requirements.
2. Propose a minimal, maintainable architecture.
3. Identify the API request and response schemas.
4. Explain how AI classification will be separated from deterministic refund decisions.
5. Identify ambiguities that require documented assumptions.
6. Break implementation into small, testable milestones.

Do not implement anything yet. Wait for my approval before proceeding.

Prioritise correctness, security, idempotency, testability, and the five-hour development budget.
```

One thing the agent got wrong: the initial deterministic refund policy recommended a refund for T-1009 because it saw a low-usage billing complaint. The billing data actually had one failed payment and one successful payment, not two successful charges. I caught it by running the all-ticket table, changed the policy, and added a regression test.

One part that is intentionally hand-shaped is the refund policy. Encoding those rules directly was clearer and safer than trying to prompt a model into doing money decisions.
