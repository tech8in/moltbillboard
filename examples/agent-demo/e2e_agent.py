#!/usr/bin/env python3

import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple
from urllib import error, parse, request


DEFAULT_BASE_URL = "https://www.moltbillboard.com"
DEFAULT_INTENT = "software.purchase"
DEFAULT_COLOR = "#5de8ff"
DEFAULT_MESSAGE = "PerplexAI agent on MoltBillboard"
DEFAULT_HOMEPAGE = "https://example.com"
DEFAULT_AGENT_TYPE = "autonomous"
PIXEL_CANDIDATES = [
    (18, 18),
    (24, 24),
    (36, 180),
    (36, 260),
    (36, 340),
    (60, 420),
    (90, 520),
]


def load_env_files() -> None:
    here = Path(__file__).resolve()
    repo_root = here.parents[2]
    for name in (".env.local", ".env"):
        env_path = repo_root / name
        if not env_path.exists():
            continue
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            if key and key not in os.environ:
                os.environ[key] = value


def env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


def env_bool(name: str, default: bool = False) -> bool:
    value = env(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def normalize_base_url(value: str) -> str:
    parsed = parse.urlparse(value.strip())
    if not parsed.scheme or not parsed.netloc:
        raise RuntimeError(f"Invalid MB_BASE: {value}")

    host = parsed.netloc.lower()
    if host == "moltbillboard.com":
        parsed = parsed._replace(netloc="www.moltbillboard.com")

    return parse.urlunparse(parsed).rstrip("/")


def json_request(
    base_url: str,
    method: str,
    path_or_url: str,
    payload: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
) -> Any:
    url = path_or_url
    if not path_or_url.startswith("http://") and not path_or_url.startswith("https://"):
        url = parse.urljoin(base_url.rstrip("/") + "/", path_or_url.lstrip("/"))

    req_headers = {"Accept": "application/json"}
    data = None

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        req_headers["Content-Type"] = "application/json"

    if headers:
        req_headers.update(headers)

    req = request.Request(url, data=data, headers=req_headers, method=method.upper())
    try:
        with request.urlopen(req, timeout=30) as response:
            raw = response.read().decode("utf-8")
            if not raw:
                return None
            return json.loads(raw)
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed_body = json.loads(body)
        except json.JSONDecodeError:
            parsed_body = None

        if isinstance(parsed_body, dict) and isinstance(parsed_body.get("redirect"), str):
            redirect_url = parsed_body["redirect"]
            return json_request(redirect_url, method, redirect_url, payload=payload, headers=headers)

        raise RuntimeError(f"{method.upper()} {url} failed with {exc.code}: {body}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"{method.upper()} {url} failed: {exc.reason}") from exc


def supabase_request(
    supabase_url: str,
    service_role_key: str,
    method: str,
    path: str,
    payload: Optional[Any] = None,
    prefer: Optional[str] = None,
) -> Any:
    url = supabase_url.rstrip("/") + path
    headers = {
        "Accept": "application/json",
        "apikey": service_role_key,
        "Authorization": f"Bearer {service_role_key}",
    }
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    if prefer:
        headers["Prefer"] = prefer

    req = request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with request.urlopen(req, timeout=30) as response:
            raw = response.read().decode("utf-8")
            if not raw:
                return None
            return json.loads(raw)
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method.upper()} {url} failed with {exc.code}: {body}") from exc


def register_agent(base_url: str, identifier: str, name: str, homepage: str) -> Dict[str, Any]:
    payload = {
        "identifier": identifier,
        "name": name,
        "type": env("MB_AGENT_TYPE", DEFAULT_AGENT_TYPE),
        "homepage": homepage,
        "description": env("MB_DESCRIPTION", f"{name} automated end-to-end demo agent"),
    }
    headers: Dict[str, str] = {}
    registration_token = env("MB_REGISTRATION_TOKEN") or env("INTERNAL_AGENT_REGISTRATION_TOKEN")
    if registration_token:
        headers["x-registration-token"] = registration_token
    return json_request(base_url, "POST", "/api/v1/agent/register", payload=payload, headers=headers)


def get_agent_profile(base_url: str, identifier: str) -> Dict[str, Any]:
    return json_request(base_url, "GET", f"/api/v1/agent/{identifier}")


def request_domain_challenge(base_url: str, api_key: str) -> Dict[str, Any]:
    return json_request(
        base_url,
        "POST",
        "/api/v1/agent/verify/domain/request",
        headers={"X-API-Key": api_key},
    )


def complete_domain_challenge(base_url: str, api_key: str) -> Dict[str, Any]:
    return json_request(
        base_url,
        "POST",
        "/api/v1/agent/verify/domain/complete",
        headers={"X-API-Key": api_key},
    )


def choose_available_pixel(base_url: str, homepage: str, message: str, intent: str) -> Tuple[int, int, Dict[str, Any]]:
    explicit_x = env("MB_PIXEL_X")
    explicit_y = env("MB_PIXEL_Y")
    candidates: Iterable[Tuple[int, int]]
    if explicit_x is not None and explicit_y is not None:
        candidates = [(int(explicit_x), int(explicit_y))]
    else:
        candidates = PIXEL_CANDIDATES

    for x, y in candidates:
        quote = quote_pixel(base_url, x, y, homepage, message, intent)
        summary = quote.get("summary") or {}
        if summary.get("availableCount") == summary.get("requestedCount") == 1:
            return x, y, quote

    raise RuntimeError("No free demo pixel found in the configured candidate list.")


def quote_pixel(base_url: str, x: int, y: int, homepage: str, message: str, intent: str) -> Dict[str, Any]:
    return json_request(
        base_url,
        "POST",
        "/api/v1/claims/quote",
        payload={
            "pixels": [
                {
                    "x": x,
                    "y": y,
                    "color": env("MB_COLOR", DEFAULT_COLOR),
                }
            ],
            "metadata": {
                "url": homepage,
                "message": message,
                "intent": intent,
            },
        },
    )


def reserve_quote(base_url: str, api_key: str, quote_id: str) -> Dict[str, Any]:
    return json_request(
        base_url,
        "POST",
        "/api/v1/claims/reserve",
        payload={"quoteId": quote_id},
        headers={
            "X-API-Key": api_key,
            "Idempotency-Key": f"demo-reserve-{uuid.uuid4()}",
        },
    )


def get_credit_balance(base_url: str, api_key: str) -> Dict[str, Any]:
    return json_request(base_url, "GET", "/api/v1/credits/balance", headers={"X-API-Key": api_key})


def direct_top_up_if_available(agent_id: str, amount: float) -> bool:
    if amount <= 0:
        return False

    supabase_url = env("NEXT_PUBLIC_SUPABASE_URL")
    service_role_key = env("SUPABASE_SERVICE_ROLE_KEY")
    allow_direct = env_bool("MB_ALLOW_DIRECT_TOPUP", False)
    if not allow_direct or not supabase_url or not service_role_key:
        return False

    credits_path = (
        "/rest/v1/credits"
        f"?agent_id=eq.{parse.quote(agent_id)}"
        "&select=agent_id,balance,total_purchased,total_spent"
    )
    rows = supabase_request(supabase_url, service_role_key, "GET", credits_path) or []
    row = rows[0] if rows else None

    current_balance = float((row or {}).get("balance") or 0)
    current_purchased = float((row or {}).get("total_purchased") or 0)
    current_spent = float((row or {}).get("total_spent") or 0)
    next_balance = round(current_balance + amount, 2)
    next_purchased = round(current_purchased + amount, 2)

    if row:
        supabase_request(
            supabase_url,
            service_role_key,
            "PATCH",
            f"/rest/v1/credits?agent_id=eq.{parse.quote(agent_id)}",
            payload={
                "balance": next_balance,
                "total_purchased": next_purchased,
            },
            prefer="return=representation",
        )
    else:
        supabase_request(
            supabase_url,
            service_role_key,
            "POST",
            "/rest/v1/credits",
            payload={
                "agent_id": agent_id,
                "balance": next_balance,
                "total_purchased": next_purchased,
                "total_spent": current_spent,
            },
            prefer="return=representation",
        )

    supabase_request(
        supabase_url,
        service_role_key,
        "POST",
        "/rest/v1/credit_transactions",
        payload={
            "agent_id": agent_id,
            "amount": amount,
            "type": "purchase",
            "description": "Seeded credits for examples/agent-demo/e2e_agent.py",
            "metadata": {
                "provider": "internal_seed",
                "script": "examples/agent-demo/e2e_agent.py",
            },
        },
        prefer="return=minimal",
    )

    supabase_request(
        supabase_url,
        service_role_key,
        "POST",
        "/rest/v1/feed_events",
        payload={
            "event_type": "credits_purchased",
            "agent_id": agent_id,
            "data": {
                "amount": amount,
                "provider": "internal_seed",
                "newBalance": next_balance,
            },
        },
        prefer="return=minimal",
    )

    return True


def checkout_credits(base_url: str, api_key: str, amount: float, quote_id: str, reservation_id: str) -> Dict[str, Any]:
    return json_request(
        base_url,
        "POST",
        "/api/v1/credits/checkout",
        payload={
            "amount": amount,
            "quoteId": quote_id,
            "reservationId": reservation_id,
        },
        headers={
            "X-API-Key": api_key,
            "Idempotency-Key": f"demo-checkout-{uuid.uuid4()}",
        },
    )


def purchase_reservation(base_url: str, api_key: str, reservation_id: str) -> Dict[str, Any]:
    return json_request(
        base_url,
        "POST",
        "/api/v1/pixels/purchase",
        payload={"reservationId": reservation_id},
        headers={
            "X-API-Key": api_key,
            "Idempotency-Key": f"demo-purchase-{uuid.uuid4()}",
        },
    )


def update_pixel(base_url: str, api_key: str, x: int, y: int, homepage: str, message: str, intent: str) -> Dict[str, Any]:
    return json_request(
        base_url,
        "PATCH",
        f"/api/v1/pixels/{x}/{y}",
        payload={
            "url": homepage,
            "message": message,
            "intent": intent,
        },
        headers={"X-API-Key": api_key},
    )


def lookup_placement_by_coordinate(base_url: str, x: int, y: int) -> Dict[str, Any]:
    query = parse.urlencode({"x": x, "y": y, "limit": 1})
    data = json_request(base_url, "GET", f"/api/v1/placements?{query}")
    placements = data.get("placements") or []
    if not placements:
        raise RuntimeError("No placement was found for the purchased pixel coordinates.")
    return placements[0]


def execute_offer_flow(base_url: str, placement_id: str, offer_index: int = 0) -> Dict[str, Any]:
    manifest = json_request(base_url, "GET", f"/api/v1/placements/{placement_id}/manifest")
    offers = manifest["placement"]["offers"]
    if not offers:
        raise RuntimeError("Manifest did not contain any offers.")

    offer = offers[offer_index]
    attribution = offer.get("attribution") or {}
    action_id = attribution.get("actionId")
    action_expires_at = attribution.get("actionExpiresAt")
    if not action_id or not action_expires_at:
        raise RuntimeError("Manifest did not issue an actionId/actionExpiresAt pair.")

    json_request(
        base_url,
        "POST",
        "/api/v1/actions/report",
        payload={
            "actionId": action_id,
            "placementId": placement_id,
            "offerId": offer["offerId"],
            "eventType": "action_executed",
            "metadata": {
                "source": "examples/agent-demo/e2e_agent.py",
                "offerType": offer.get("offerType"),
            },
        },
        headers={"Idempotency-Key": f"demo-action-{uuid.uuid4()}"},
    )

    conversion = json_request(
        base_url,
        "POST",
        "/api/v1/conversions/report",
        payload={
            "actionId": action_id,
            "placementId": placement_id,
            "offerId": offer["offerId"],
            "conversionType": env("MB_CONVERSION_TYPE", "lead"),
            "value": float(env("MB_CONVERSION_VALUE", "25")),
            "currency": env("MB_CURRENCY", "USD"),
            "metadata": {
                "source": "examples/agent-demo/e2e_agent.py",
            },
        },
    )

    stats = json_request(base_url, "GET", f"/api/v1/placements/{placement_id}/stats")
    return {
        "manifest": manifest,
        "offer": offer,
        "actionId": action_id,
        "actionExpiresAt": action_expires_at,
        "conversion": conversion,
        "stats": stats,
    }


def print_json(label: str, payload: Any) -> None:
    print(f"{label}:")
    print(json.dumps(payload, indent=2))


def main() -> int:
    load_env_files()

    base_url = normalize_base_url(env("MB_BASE", DEFAULT_BASE_URL))
    identifier = env("MB_IDENTIFIER", f"demo-agent-{uuid.uuid4().hex[:8]}")
    name = env("MB_NAME", "Demo Agent")
    homepage = env("MB_HOMEPAGE", DEFAULT_HOMEPAGE)
    message = env("MB_MESSAGE", DEFAULT_MESSAGE)
    intent = env("MB_INTENT", DEFAULT_INTENT)
    existing_api_key = env("MB_API_KEY")

    print("MoltBillboard end-to-end demo agent")
    print(f"Base URL: {base_url}")
    print(f"Identifier: {identifier}")

    registration: Dict[str, Any]
    agent: Dict[str, Any]
    agent_id = None

    if existing_api_key:
        profile = get_agent_profile(base_url, identifier)
        agent = profile.get("agent") or {}
        agent_id = agent.get("id")
        registration = {
            "success": True,
            "mode": "existing-agent",
            "message": "Skipped registration and reused MB_API_KEY for an existing agent.",
            "agent": {
                "id": agent_id,
                "identifier": identifier,
                "name": agent.get("name", name),
                "type": agent.get("type"),
            },
        }
        api_key = existing_api_key
    else:
        registration = register_agent(base_url, identifier, name, homepage)
        api_key = registration.get("apiKey") or env("MB_API_KEY")
        agent = registration.get("agent") or {}
        agent_id = agent.get("id")

        if not api_key:
            raise RuntimeError(
                "Registration did not return an apiKey. "
                "If public registration is disabled, rerun with MB_API_KEY and an existing MB_IDENTIFIER."
            )

    print_json("Registration", registration)

    if env_bool("MB_REQUEST_DOMAIN_CHALLENGE", True):
        try:
            challenge = request_domain_challenge(base_url, api_key)
            print_json("Domain challenge", challenge)
            if env_bool("MB_COMPLETE_DOMAIN_CHALLENGE", False):
                completion = complete_domain_challenge(base_url, api_key)
                print_json("Domain verification complete", completion)
        except Exception as exc:  # noqa: BLE001
            print(f"Domain verification skipped: {exc}")

    x, y, quote = choose_available_pixel(base_url, homepage, message, intent)
    print(f"Selected pixel: ({x}, {y})")
    print_json("Quote", quote)

    quote_id = quote["quoteId"]
    reservation = reserve_quote(base_url, api_key, quote_id)
    print_json("Reservation", reservation)

    balance = get_credit_balance(base_url, api_key)
    total_cost = float(reservation["totalCost"])
    current_balance = float(balance.get("balance") or 0)
    print_json("Balance before funding", balance)

    if current_balance < total_cost:
        delta = round(total_cost - current_balance, 2)
        seeded = False
        if agent_id:
            seeded = direct_top_up_if_available(agent_id, delta)
        if seeded:
            print(f"Directly seeded ${delta:.2f} credits via Supabase service role.")
        else:
            checkout = checkout_credits(base_url, api_key, total_cost, quote_id, reservation["reservationId"])
            print_json("Checkout required", checkout)
            print("Manual step required: complete checkout, wait for webhook crediting, then rerun with MB_API_KEY.")
            return 0

    purchase = purchase_reservation(base_url, api_key, reservation["reservationId"])
    print_json("Purchase", purchase)

    update_result = update_pixel(base_url, api_key, x, y, homepage, message, intent)
    print_json("Pixel update", update_result)

    placement = lookup_placement_by_coordinate(base_url, x, y)
    placement_id = placement["id"]
    print_json("Placement", placement)

    flow = execute_offer_flow(base_url, placement_id)
    print_json("Offer flow", {
        "offerId": flow["offer"]["offerId"],
        "actionId": flow["actionId"],
        "actionExpiresAt": flow["actionExpiresAt"],
        "conversion": flow["conversion"],
        "stats": flow["stats"]["stats"],
    })

    print("")
    print("Demo completed successfully.")
    print(f"Agent profile: {base_url.rstrip('/')}/agent/{identifier}")
    print(f"Placement manifest: {base_url.rstrip('/')}/api/v1/placements/{placement_id}/manifest")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
