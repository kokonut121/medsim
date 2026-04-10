from __future__ import annotations

import logging
from typing import Any

import httpx


logger = logging.getLogger(__name__)


class FHIRRepositoryClient:
    def __init__(
        self,
        *,
        base_url: str,
        username: str,
        password: str,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._auth = httpx.BasicAuth(username=username, password=password)
        self._timeout = timeout_seconds

    def get_resource(self, resource_type: str, resource_id: str) -> dict[str, Any] | None:
        response = httpx.get(
            f"{self.base_url}/{resource_type}/{resource_id}",
            auth=self._auth,
            headers={"Accept": "application/fhir+json"},
            timeout=self._timeout,
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    def put_resource(self, resource: dict[str, Any]) -> dict[str, Any]:
        resource_type = resource["resourceType"]
        resource_id = resource["id"]
        response = httpx.put(
            f"{self.base_url}/{resource_type}/{resource_id}",
            auth=self._auth,
            headers={
                "Accept": "application/fhir+json",
                "Content-Type": "application/fhir+json",
            },
            json=resource,
            timeout=self._timeout,
        )
        response.raise_for_status()
        return response.json()

    def push_bundle(self, resources: list[dict[str, Any]], *, target_base: str) -> dict[str, Any]:
        target = target_base.rstrip("/")
        pushed: list[str] = []
        for resource in resources:
            resource_type = resource["resourceType"]
            resource_id = resource["id"]
            response = httpx.put(
                f"{target}/{resource_type}/{resource_id}",
                headers={
                    "Accept": "application/fhir+json",
                    "Content-Type": "application/fhir+json",
                },
                json=resource,
                timeout=self._timeout,
            )
            response.raise_for_status()
            pushed.append(f"{resource_type}/{resource_id}")
        logger.info("Pushed %s FHIR resources to %s", len(pushed), target)
        return {"status": "pushed", "target": target, "resources": pushed}
