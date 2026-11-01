import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from tenant_provisioner import PaymentEvent, TenantProvisionRequest, provision_tenant


class FakeClient:
    def __init__(self):
        self.calls = []

    def add_domain(self, domain):
        self.calls.append(("domain", domain))
        return {"ok": True, "data": {"zone_id": "zone-fin-7"}}

    def upsert_record(self, zone_id, name, content, idempotency_key):
        self.calls.append(("record", zone_id, name, content, idempotency_key))
        return {"ok": True, "data": {}}

    def presign_asset(self, bucket, key, host):
        self.calls.append(("asset", bucket, key, host))
        return {"ok": True, "data": {"url": "https://assets.example/signed"}}


def test_low_risk_payment_provisions_host_and_asset():
    client = FakeClient()
    result = provision_tenant(TenantProvisionRequest("acme", "example.test", "app.example.net"), PaymentEvent("pay-1", "acme", 12500, 12), client, "receipts")
    assert result["status"] == "provisioned"
    assert result["hostname"] == "acme.example.test"
    assert client.calls[1] == ("record", "zone-fin-7", "acme.example.test", "app.example.net", "pay-1")
    assert client.calls[2] == ("asset", "receipts", "acme.example.test/receipt.json", "acme.example.test")
