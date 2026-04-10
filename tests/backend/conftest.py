from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.db.iris_client import IRISClient, iris_client
from backend.main import app


@pytest.fixture()
def client():
    """Fresh TestClient backed by the shared in-memory iris_client."""
    return TestClient(app)


@pytest.fixture()
def fresh_iris(monkeypatch):
    """
    Replace the shared iris_client singleton with a brand-new instance for
    tests that need an isolated, predictable store.
    """
    new_client = IRISClient()
    monkeypatch.setattr("backend.db.iris_client.iris_client", new_client)
    # Also patch every module that already imported iris_client directly
    for module in (
        "backend.api.facilities",
        "backend.api.scans",
        "backend.api.reports",
        "backend.api.models",
        "backend.api.fhir",
        "backend.agents.orchestrator",
    ):
        try:
            import importlib
            mod = importlib.import_module(module)
            if hasattr(mod, "iris_client"):
                monkeypatch.setattr(mod, "iris_client", new_client)
        except ModuleNotFoundError:
            pass
    return new_client


@pytest.fixture()
def seeded_unit_id():
    """Unit ID that exists in the default demo seed data."""
    return "unit_1"


@pytest.fixture()
def demo_world_model():
    """Minimal world model dict accepted by agent run() functions."""
    return {
        "units": [
            {
                "unit_id": "unit_1",
                "unit_type": "ED",
                "rooms": [
                    {
                        "room_id": "R101",
                        "type": "patient_room",
                        "area_sqft_estimate": 180,
                        "equipment": [
                            {"type": "crash_cart", "position": "north corridor", "accessible": True, "confidence": 0.9}
                        ],
                        "sightline_to_nursing_station": False,
                    }
                ],
            }
        ],
        "flow_annotations": {
            "patient_flow_paths": [["ENTRY", "R101"]],
            "staff_flow_paths": [["DESK", "R101"]],
            "clean_corridors": ["C1"],
            "dirty_corridors": ["C2"],
        },
    }
