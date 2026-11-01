# Expense claim approval: how one claim moves through Ledgerly

Research notes, 2026-10-30, from the Ledgerly v4.2 code and the ops runbook. Marks: [✓] read in code and re-checked, [code] traced, [docs] runbook only.

Paths: `A/` = `apps/mobile/src/`, `B/` = `services/claims/src/`, `P/` = `services/payments/src/`.

## The flow

1. The employee photographs a receipt in the mobile app and fills amount, currency, category and a note. The app runs OCR on the device and pre-fills amount and date; the employee can overwrite both. Nothing leaves the phone until Submit. [✓] `A/claims/NewClaim.tsx`, `A/ocr/receipt.ts`
2. Submit uploads the photo to object storage first (presigned URL from `POST /uploads`), then sends `POST /claims` with `{ amount, currency, category, note, receiptKey, ocr: { amount, date, confidence } }`. If the upload fails the claim is kept as a local draft and retried on the next app start. [✓] `A/claims/submit.ts`
3. The claims service validates the payload (zod; amount > 0, currency in the company list, note ≤ 500 chars), checks that the employee belongs to an active cost centre, and writes the claim with status `submitted`. Duplicate detection: same employee, same amount, same receipt date within 3 days → status `flagged-duplicate` instead, and the employee gets a push notification. [✓] `B/http/createClaim.ts`, `B/rules/duplicate.ts`
4. A policy engine runs synchronously inside the same request: per-category limits, per-diem rules, "receipt required above 25 EUR", "alcohol never". Each rule returns pass, warn or block. A block sets status `rejected-policy` with the rule id; a warn is stored on the claim and shown to the approver. The engine never calls out. [code] `B/policy/engine.ts`, `B/policy/rules/*.ts`
5. The claim is routed to an approver: the employee's manager, unless the amount is above the manager's approval limit, in which case the manager's manager, up to three levels; above that, finance. Routing reads the org chart from the HR system over HTTP (`GET /org/{employeeId}/chain`), cached 15 minutes. If HR is down and the cache is cold the claim stays `submitted` and a retry job runs every 5 minutes. [code] `B/routing/route.ts`, `B/jobs/retryRouting.ts`
6. The approver gets an email and a push; the approval page shows the receipt, the OCR confidence, the policy warnings and the employee's last 90 days of claims in the same category. The approver can approve, reject with a reason, or send back for more information. A claim nobody touches for 7 days is escalated one level and the approver is reminded daily. [docs] runbook §4; `B/notify/approverNotice.ts`
7. On approve, the claim becomes `approved` and a payment instruction is published to the payments service over the message bus (`claims.approved` event with claim id, employee bank token, amount, currency). The claims service never talks to the bank. [✓] `B/http/decide.ts`, `B/bus/publish.ts`
8. The payments service batches approved claims per currency and runs the batch at 16:00 local time on working days through the bank API (`POST /v2/payments/batch`). A batch is signed with the company HSM key. The bank answers asynchronously with a webhook per payment: `accepted`, `rejected` (bad IBAN, closed account) or `returned` (up to 5 days later). [code] `P/batch/run.ts`, `P/bank/client.ts`, `P/bank/webhook.ts`
9. On `accepted` the claim becomes `paid` and the employee gets a push with the expected date. On `rejected` the claim becomes `payment-failed`, finance gets a ticket, and the employee is asked to check their bank details; a corrected claim is re-queued without going through approval again. On `returned` the same happens, plus the ledger entry is reversed. [code] `P/bank/webhook.ts`, `B/http/paymentStatus.ts`
10. Every status change writes an audit row (`claim_events`: who, when, from, to, reason) and the ledger service posts a journal entry on `approved` (accrual) and on `paid` (settlement). Audit rows are kept 10 years; receipts 7. [docs] runbook §7; `B/audit/write.ts`

## Branches and limits worth knowing

* OCR confidence below 0.6 does not block anything; it is only shown to the approver. [✓]
* Amounts in a currency the company does not use are rejected at step 3, not converted. [✓]
* The policy engine is the only place rules live; the approval page shows warnings but cannot override a block. [code]
* Routing picks the approver once. A manager change after submission does not re-route unless the claim is sent back and resubmitted. [code]
* The 16:00 batch is per currency and per legal entity; a claim approved at 16:01 waits a day. There is no "pay now". [docs]
* The bank webhook has no replay protection beyond an HMAC check; duplicate webhooks are deduplicated by payment id. [code]
* Send-back resets the claim to `draft` on the employee's phone; the history is kept, the approver chain is recomputed on resubmit. [code]

## Other callers of the same pieces

* The web portal (`apps/web`) submits claims through the same `POST /claims` and the same policy engine; it skips OCR (manual entry only).
* The monthly "card statement import" job creates claims in bulk through `B/http/createClaim.ts` with `source: "card"`; those skip duplicate detection and go straight to the employee as `draft` to be completed.
