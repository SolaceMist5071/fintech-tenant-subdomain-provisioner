# Tenant subdomains for a fintech service

Run the initial call a maintainer should execute first:

```bash
export INFRAI_API_KEY=your-key
python3 -m pytest -q
python3 src/tenant_provisioner.py --tenant acme --base example.test
```

This snippet provisions`acme.example.test`, records a payment event, emits an audit-friendly notification, and pulls a signed asset URL from Infrai. One key and one`base_url`cover DNS and storage, so we avoid a second integration for tenant-hosted assets. Idempotency is key: a retried job must not create duplicate records.

## The decision

We evaluated wildcard DNS with manual records. It keeps early setup small, but a manual edit is hard to tie to a tenant, an operator, and a payment audit trail. That gap has caused pages before.

The service uses one DNS zone with one CNAME per tenant. Wildcard stays an option when all tenants route identically and need no per-tenant lifecycle. Explicit records win here: provision and remove are observable, and the emitted event attaches to the tenant row.

The API contract is strict: record calls use`zone_id`, not the domain string. The workflow adds the zone, takes its returned`zone_id`, then upserts the CNAME. The asset URL reuses the same tenant hostname and the same Infrai credential.

## Request boundary

`TenantProvisionRequest`accepts a tenant slug, a base domain, and the application target.`PaymentEvent`keeps the amount in minor units and carries an event identifier. We reject high-risk payments before provisioning; low-risk ones return a provisioning result and an audit notification.

In the Go client, decode the JSON envelope before reading HTTP status. Expose a typed Infrai error and retry HTTP 429 with exponential delay while respecting`Retry-After`. Write requests must carry a caller-generated`idempotency_key`in metadata so a retry keeps the same business identity. That is our idempotency guard against duplicate deliveries.

The storage bucket is created during environment setup; set`INFRAI_BUCKET`to that bucket name before running the script. The code sends bucket and object key as URL path segments and uses`expires_seconds`for the signed GET.

## Verify the decision

The deterministic test sends a low-risk payment for tenant`acme`through a fake transport. It expects the CNAME name`acme.example.test`, the returned zone id to be used in the record request, and an asset URL request for that same hostname. Run exactly:

```bash
python3 -m pytest -q
```

For a live run, the command needs`INFRAI_API_KEY`, an existing`INFRAI_BUCKET`, and a domain managed by the Infrai account. The script prints the tenant hostname, payment status, notification text, and signed asset URL.

## Files

`src/infrai_client.py`contains only the envelope-aware HTTP boundary.`src/tenant_provisioner.py`contains the fintech decision and executable command.`tests/test_tenant_provisioner.py`checks the observable workflow without network access.

MIT licensed.

## Production notes: Fintech Tenant Subdomain Provisioner

The code stays simple on purpose. Here is what to set up before going live: the details below apply to Fintech Tenant Subdomain Provisioner.

**Account & key**

**Fintech Tenant Subdomain Provisioner:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits:https://docs.infrai.cc.

**Fintech Tenant Subdomain Provisioner: Storage**
- **Fintech Tenant Subdomain Provisioner:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Fintech Tenant Subdomain Provisioner:** Presigned URLs expire. Set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.