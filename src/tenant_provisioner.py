from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass

from infrai_client import InfraiClient


@dataclass(frozen=True)
class TenantProvisionRequest:
    tenant_slug: str
    base_domain: str
    application_target: str


@dataclass(frozen=True)
class PaymentEvent:
    event_id: str
    tenant_slug: str
    amount_minor: int
    risk_score: int


def provision_tenant(request: TenantProvisionRequest, payment: PaymentEvent, client: InfraiClient, bucket: str) -> dict[str, str]:
    if payment.tenant_slug != request.tenant_slug:
        raise ValueError("payment tenant does not match request")
    if payment.risk_score >= 70:
        return {"status": "rejected", "notification": f"Payment {payment.event_id} requires manual review."}
    host = f"{request.tenant_slug}.{request.base_domain}"
    zone = client.add_domain(request.base_domain)
    zone_id = zone["data"]["zone_id"]
    client.upsert_record(zone_id, host, request.application_target, payment.event_id)
    asset = client.presign_asset(bucket, f"{host}/receipt.json", host)
    return {"status": "provisioned", "hostname": host, "notification": f"Payment {payment.event_id} provisioned {host}.", "asset_url": asset["data"]["url"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--base", required=True)
    args = parser.parse_args()
    client = InfraiClient()
    payment = PaymentEvent(event_id=f"tenant-{args.tenant}", tenant_slug=args.tenant, amount_minor=12500, risk_score=12)
    result = provision_tenant(TenantProvisionRequest(args.tenant, args.base, os.environ.get("APP_TARGET", "app.example.net")), payment, client, os.environ["INFRAI_BUCKET"])
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(__file__))
    main()
