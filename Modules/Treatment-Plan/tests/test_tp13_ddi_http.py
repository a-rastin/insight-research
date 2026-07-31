import base64
import hashlib
import hmac
import json
import unittest

import httpx

from treatment_plan.clinical_context import OutboundRequestContext
from treatment_plan.ddi_check import HttpDdiPort


class DdiHttpPortTests(unittest.IsolatedAsyncioTestCase):
    async def test_signs_canonical_ddi_v1_request_and_forwards_only_session_cookie(self):
        secret = b"test-only-ddi-service-secret-000000000000"
        context = OutboundRequestContext(
            "opaque-session",
            "00000000-0000-4000-8000-000000000091",
            "00000000-0000-4000-8000-000000000092",
        )
        request_body = {
            "schemaVersion": "1.0.0",
            "idempotencyKey": "sha256:" + "a" * 64,
            "planSemanticHash": "sha256:" + "b" * 64,
            "medicationSetHash": "sha256:" + "c" * 64,
            "medications": [{"inputIndex": 0, "source": "proposed", "originalText": "Synthetic A"}],
        }

        async def handler(request: httpx.Request) -> httpx.Response:
            body = await request.aread()
            self.assertEqual("/api/ddi/v1/checks", request.url.path)
            self.assertEqual("insight_session=opaque-session", request.headers["Cookie"])
            self.assertEqual(request_body, json.loads(body))
            content_hash = hashlib.sha256(body).hexdigest()
            canonical = "\n".join((
                "INSIGHT-HMAC-V1",
                "treatment-plan",
                "tp-ddi-v1",
                request.headers["X-Insight-Timestamp"],
                request.headers["X-Insight-Nonce"],
                "ddi-checker",
                "POST",
                "/api/ddi/v1/checks",
                content_hash,
                request.headers["X-Request-ID"],
                context.correlation_id,
                context.parent_request_id,
            )).encode()
            expected = base64.urlsafe_b64encode(hmac.new(secret, canonical, hashlib.sha256).digest()).rstrip(b"=").decode()
            self.assertEqual(content_hash, request.headers["X-Insight-Content-SHA256"])
            self.assertEqual(f"v1={expected}", request.headers["X-Insight-Signature"])
            return httpx.Response(201, headers={"X-Schema-Version": "1.0.0"}, json={"schemaVersion": "1.0.0"})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            port = HttpDdiPort(
                "http://127.0.0.1:8107", "treatment-plan", "tp-ddi-v1", secret,
                client=client,
            )
            self.assertEqual({"schemaVersion": "1.0.0"}, await port.check(request_body, context))

    async def test_readiness_requires_exact_ddi_v1_ready_contract(self):
        async def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, headers={"X-Schema-Version": "1.0.0"}, json={
                "status": "ready", "module": "ddi-checker", "schemaVersion": "1.0.0",
                "knowledgeBaseVersion": "1.2.3", "knowledgeBaseContentHash": "sha256:" + "d" * 64,
            })

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            port = HttpDdiPort(
                "http://127.0.0.1:8107", "treatment-plan", "tp-ddi-v1",
                b"test-only-ddi-service-secret-000000000000", client=client,
            )
            self.assertTrue(await port.ready())


if __name__ == "__main__":
    unittest.main()
