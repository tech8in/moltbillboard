#!/usr/bin/env python3

import json
import os
import sys
import uuid
from typing import Any, Dict, Iterable, Optional
from urllib import error, parse, request


INTENTS = [
    "travel.booking.flight",
    "travel.booking.hotel",
    "food.delivery",
    "transport.ride_hailing",
    "software.purchase",
    "subscription.register",
    "freelance.hiring",
    "commerce.product_purchase",
    "finance.loan_application",
    "finance.insurance_quote",
]


def env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


def api_request(base_url: str, method: str, path_or_url: str, payload: Optional[Dict[str, Any]] = None,
                headers: Optional[Dict[str, str]] = None) -> Any:
    url = path_or_url if path_or_url.startswith("http://") or path_or_url.startswith("https://") else parse.urljoin(base_url, path_or_url)
    data = None
    req_headers = {"Accept": "application/json"}

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        req_headers["Content-Type"] = "application/json"

    if headers:
        req_headers.update(headers)

    req = request.Request(url, data=data, headers=req_headers, method=method.upper())
    try:
        with request.urlopen(req, timeout=20) as response:
            raw = response.read().decode("utf-8")
            if not raw:
                return None
            return json.loads(raw)
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method.upper()} {url} failed with {exc.code}: {body}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"{method.upper()} {url} failed: {exc.reason}") from exc


def discover_first_placement(base_url: str, requested_intent: Optional[str]) -> Dict[str, Any]:
    intents: Iterable[str] = [requested_intent] if requested_intent else INTENTS

    for intent in intents:
        query = parse.urlencode({"intent": intent, "limit": 1})
        data = api_request(base_url, "GET", f"/api/v1/placements?{query}")
        placements = data.get("placements", [])
        if placements:
            return {"intent": intent, "placement": placements[0]}

    raise RuntimeError("No live placements found for the requested discovery intents.")


def main() -> int:
    base_url = env("MB_BASE", "https://www.moltbillboard.com")
    requested_intent = env("MB_INTENT")
    conversion_type = env("MB_CONVERSION_TYPE", "lead")
    conversion_value = float(env("MB_CONVERSION_VALUE", "25"))
    currency = env("MB_CURRENCY", "USD")

    print("MoltBillboard agent demo")
    print(f"Base URL: {base_url}")

    discovered = discover_first_placement(base_url, requested_intent)
    placement = discovered["placement"]
    placement_id = placement["id"]
    intent = discovered["intent"]

    print(f"Discovered placement: {placement_id}")
    print(f"Intent: {intent}")

    manifest = api_request(base_url, "GET", f"/api/v1/placements/{placement_id}/manifest")
    offers = manifest["placement"]["offers"]
    if not offers:
      raise RuntimeError("Manifest did not contain any offers.")

    offer = offers[0]
    attribution = offer.get("attribution") or {}
    action_id = attribution.get("actionId")
    action_expires_at = attribution.get("actionExpiresAt")
    offer_id = offer["offerId"]

    if not action_id or not action_expires_at:
        raise RuntimeError("Manifest offer attribution is missing actionId or actionExpiresAt.")

    print(f"Selected offer: {offer_id}")
    print(f"Action ID: {action_id}")
    print(f"Action expires at: {action_expires_at}")

    action_result = api_request(
        base_url,
        "POST",
        "/api/v1/actions/report",
        payload={
            "actionId": action_id,
            "placementId": placement_id,
            "offerId": offer_id,
            "eventType": "action_executed",
            "metadata": {
                "source": "examples/agent-demo",
                "intent": intent,
            },
        },
        headers={
            "Idempotency-Key": f"agent-demo-action-{uuid.uuid4()}",
        },
    )
    print(f"Action executed: {action_result['success']}")

    conversion_result = api_request(
        base_url,
        "POST",
        "/api/v1/conversions/report",
        payload={
            "actionId": action_id,
            "placementId": placement_id,
            "offerId": offer_id,
            "conversionType": conversion_type,
            "value": conversion_value,
            "currency": currency,
            "metadata": {
                "source": "examples/agent-demo",
                "intent": intent,
            },
        },
    )
    print(f"Conversion reported: {conversion_result['success']}")

    stats_result = api_request(base_url, "GET", f"/api/v1/placements/{placement_id}/stats")
    stats = stats_result["stats"]
    print("Stats snapshot:")
    print(f"  offer_discovered: {stats['byType'].get('offer_discovered', 0)}")
    print(f"  action_executed: {stats['byType'].get('action_executed', 0)}")
    print(f"  conversion_reported: {stats['byType'].get('conversion_reported', 0)}")
    print(f"  conversion_count: {stats.get('conversionCount', 0)}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
