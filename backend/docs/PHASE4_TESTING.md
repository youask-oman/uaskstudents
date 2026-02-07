# Phase 4 Testing Plan: Stripe Payments

## 1. Unit Tests (Mocked Stripe)
Run the following tests to verify idempotency and fulfillment logic:
```bash
pytest tests/test_stripe_webhooks.py
```
*   **Case 1: Idempotency**. Send the same `checkout.session.completed` event twice. Verify only one `CreditLot` and `Payment` record exists.
*   **Case 2: Out-of-order**. Send `payment_intent.succeeded` before `checkout.session.completed`. Verify fulfillment happens on the first successful signal.
*   **Case 3: Failure**. Send `payment_intent.payment_failed`. Verify `TopUpOrder` status is `FAILED`.

## 2. Integration Testing (Stripe CLI)
To test the real flow with Stripe Test Mode:
1.  **Start Stripe Listen**:
    ```bash
    stripe listen --forward-to localhost:8000/api/v1/stripe/webhook
    ```
2.  **Trigger Checkout**:
    - Use the Admin Dashboard or `POST /topups/stripe/checkout` with a valid `product_code`.
    - Use the success/cancel URLs: `http://localhost:3000/topup/success` and `http://localhost:3000/topup/cancel`.
3.  **Complete Payment**: Use Stripe test cards (e.g., 4242...).
4.  **Verify Fulfillment**:
    - Check `StripeEvent` table in Admin Dashboard.
    - Verify `CreditLot` added to user balance.
    - Verify `Payment` record status is `SUCCEEDED`.

## 3. Reconciliation Test
Manually run the reconciliation job to verify detection:
```bash
python -m app.jobs.stripe_reconciliation_job
```
- Simulate a failure by manually deleting a local `Payment` record that has a corresponding Stripe PI.
- Verify a `SystemErrorEntry` is created with level `ERROR`.

## 4. Replay Test
1.  Find a `FAILED` or `RECEIVED` event in the Admin "Stripe Events" tab.
2.  Click **Replay**.
3.  Verify the event is processed and status updates to `PROCESSED`.
