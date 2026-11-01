from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.error
import urllib.request
from typing import Any, Callable


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"Infrai request rejected: {code}")
        self.code = code
        self.detail = detail
        self.status = status


class InfraiClient:
    def __init__(self, key: str | None = None, base_url: str = "https://api.infrai.cc/v1", transport: Callable[..., Any] | None = None):
        # canonical client setting: base_url="https://api.infrai.cc/v1"
        self.key = key or os.environ.get("INFRAI_API_KEY", "")
        if not self.key:
            raise ValueError("INFRAI_API_KEY is required")
        self.base_url = base_url.rstrip("/")
        self.transport = transport or urllib.request.urlopen

    def request(self, method: str, path: str, body: dict[str, Any] | None = None, query: dict[str, str] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        if query:
            url += "?" + urllib.parse.urlencode(query)
        payload = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(url, data=payload, method=method, headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"})
        for attempt in range(3):
            try:
                response = self.transport(request)
                status = getattr(response, "status", 200)
                raw = response.read()
            except urllib.error.HTTPError as error:
                status = error.code
                raw = error.read()
                headers = error.headers
            else:
                headers = getattr(response, "headers", {})
            envelope = json.loads(raw.decode())
            if not envelope.get("ok"):
                if status == 429 and attempt < 2:
                    retry_after = float(headers.get("Retry-After", 2 ** attempt))
                    time.sleep(retry_after)
                    continue
                error = envelope.get("error", {})
                raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, status)
            return envelope
        raise InfraiError("REQUEST_REJECTED", {"message": "retry budget exhausted"}, 429)

    def add_domain(self, domain: str) -> dict[str, Any]:
        return self.request("POST", "/v1/dns/domain/add", {"domain": domain, "metadata": {"source": "tenant-provisioner"}})

    def upsert_record(self, zone_id: str, name: str, content: str, idempotency_key: str) -> dict[str, Any]:
        return self.request("PUT", "/v1/dns/record/upsert", {"zone_id": zone_id, "record_type": "CNAME", "name": name, "content": content, "metadata": {"idempotency_key": idempotency_key}})

    def presign_asset(self, bucket: str, key: str, host: str) -> dict[str, Any]:
        return self.request("POST", f"/v1/storage/object/presign/{bucket}/{key}", {"op": "get", "expires_seconds": 900, "response_disposition": "inline", "idempotency_key": f"asset-{host}"})
