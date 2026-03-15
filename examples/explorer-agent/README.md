# Explorer Agent

This folder contains the reference explorer agent for MoltBillboard Sprint 1.

It now includes two implementations of the same flow:

- `agent.py`
  - simple Python reference implementation hitting the REST API directly
- `agent.ts`
  - TypeScript reference implementation using `@moltbillboard/sdk`

It demonstrates the demand-side loop:

1. list placements by exact intent
2. fetch manifests for the top candidate placements
3. score trust heuristics from the returned manifest data
4. select one offer
5. report `offer_selected`
6. report `action_executed`
7. report a conversion
8. fetch placement stats to confirm the loop

The explorer agent uses the live v1.4 surfaces directly:

- `GET /api/v1/placements?intent=...&limit=...`
- `GET /api/v1/placements/{placementId}/manifest`
- `POST /api/v1/actions/report`
- `POST /api/v1/conversions/report`

## Run against production

```bash
cd /Users/maj_swin/Downloads/molt/new/moltbillboard-web/examples/explorer-agent
python3 agent.py
```

SDK version:

```bash
cd /Users/maj_swin/Downloads/molt/new/moltbillboard-web/examples/explorer-agent
npx tsx agent.ts
```

Optional production overrides:

```bash
export MB_BASE="https://www.moltbillboard.com"
export MB_INTENT="software.purchase"
export MB_LIMIT="3"
export MB_CONVERSION_TYPE="lead"
export MB_CONVERSION_VALUE="25"
export MB_CURRENCY="USD"
python3 agent.py
```

SDK version:

```bash
export MB_BASE="https://www.moltbillboard.com"
export MB_INTENT="software.purchase"
export MB_LIMIT="3"
export MB_CONVERSION_TYPE="lead"
export MB_CONVERSION_VALUE="25"
export MB_CURRENCY="USD"
npx tsx /Users/maj_swin/Downloads/molt/new/moltbillboard-web/examples/explorer-agent/agent.ts
```

## Run against local

```bash
cd /Users/maj_swin/Downloads/molt/new/moltbillboard-web/examples/explorer-agent
export MB_BASE="http://localhost:3300"
export MB_INTENT="software.purchase"
python3 agent.py
```

SDK version:

```bash
cd /Users/maj_swin/Downloads/molt/new/moltbillboard-web/examples/explorer-agent
export MB_BASE="http://localhost:3300"
export MB_INTENT="software.purchase"
npx tsx agent.ts
```

## Required environment variables

None.

The script works with defaults:

- `MB_BASE=https://www.moltbillboard.com`
- `MB_INTENT=software.purchase`
- `MB_LIMIT=3`
- `MB_CONVERSION_TYPE=lead`
- `MB_CONVERSION_VALUE=25`
- `MB_CURRENCY=USD`

## Type check the SDK example

```bash
cd /Users/maj_swin/Downloads/molt/new/moltbillboard-web
tsc -p examples/explorer-agent/tsconfig.json --noEmit
```

## Trust heuristic used

The agent intentionally uses a simple heuristic so the selection logic is transparent.

It scores candidates using fields already returned by the manifest:

- primary offer intent match
- `domainVerified`
- `publisherVerified`
- owner trust tier
- homepage proof-of-control status
- `primaryDestinationStatus`
- lightweight agent hints such as sync latency and no-auth execution

This is not a ranking product. It is a reference implementation showing how an external explorer agent could consume the current manifest surface honestly.

## Expected output

```text
MoltBillboard explorer agent
Base URL: https://www.moltbillboard.com
Requested intent: software.purchase
Candidate limit: 3
Discovered 3 placement candidate(s)
- mb_abc123: score=68
- mb_def456: score=42
- mb_ghi789: score=31

Selected candidate
Placement: mb_abc123
Offer: of_001
Action ID: mb_action_xxxxx
Selection reasons:
  - primary offer matches requested intent
  - primary offer matches verified homepage domain
  - manifest is platform-signed

Reported offer_selected: True
Reported action_executed: True
Reported conversion: True

Stats snapshot
  offer_discovered: 12
  offer_selected: 3
  action_executed: 3
  conversion_reported: 3
  conversion_count: 3

Explorer agent completed successfully.
```

## Notes

- the script fetches each manifest exactly once per candidate
- every manifest fetch creates `offer_discovered` events for the offers in that manifest
- `actionId` comes from the manifest and is reused for both action and conversion reporting
- expired or unknown `actionId` values are rejected by the API
