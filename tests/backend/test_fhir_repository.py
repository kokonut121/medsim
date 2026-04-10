from __future__ import annotations

import httpx

from backend.db.fhir_repository import FHIRRepositoryClient


def test_put_resource_accepts_empty_success_body(monkeypatch):
    client = FHIRRepositoryClient(
        base_url="http://example.test/fhir/r4",
        username="medsent_app",
        password="changeme",
    )
    resource = {"resourceType": "Observation", "id": "finding-123", "status": "final"}

    def fake_put(*args, **kwargs):
        request = httpx.Request("PUT", "http://example.test/fhir/r4/Observation/finding-123")
        return httpx.Response(
            200,
            request=request,
            headers={
                "content-type": "text/html; charset=utf-8",
                "location": "http://example.test/fhir/r4/Observation/finding-123/_history/1",
            },
            content=b"",
        )

    monkeypatch.setattr(httpx, "put", fake_put)

    stored = client.put_resource(resource)

    assert stored == resource
