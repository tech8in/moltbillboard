# Agent Demo

This example runs the minimal MoltBillboard agent loop:

1. discover a placement by intent
2. fetch one manifest
3. select the first offer
4. report `action_executed`
5. report a conversion
6. fetch placement stats

It intentionally fetches the manifest once so the demo does not create extra `offer_discovered` events.

## Run

```bash
cd /Users/maj_swin/Downloads/molt/new/moltbillboard-web/examples/agent-demo
python3 agent.py
```

Optional environment variables:

```bash
export MB_BASE="https://www.moltbillboard.com"
export MB_INTENT="travel.booking.flight"
export MB_CONVERSION_TYPE="lead"
export MB_CONVERSION_VALUE="25"
export MB_CURRENCY="USD"
python3 agent.py
```

If `MB_INTENT` is not set, the script walks the v1 intent taxonomy until it finds a live placement.

## Expected output

```text
MoltBillboard agent demo
Base URL: https://www.moltbillboard.com
Discovered placement: pl_...
Intent: travel.booking.flight
Selected offer: of_...
Action ID: mb_action_...
Action expires at: 2026-03-15T...
Action executed: True
Conversion reported: True
Stats snapshot:
  offer_discovered: 1
  action_executed: 1
  conversion_reported: 1
  conversion_count: 1
```

## Notes

- `actionId` must come from a manifest-issued `offer_discovered` event.
- expired action IDs are rejected by both action and conversion reporting
- the placement stats endpoint is the fastest way to verify the loop without opening the database
