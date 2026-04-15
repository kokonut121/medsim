import json

import pytest

from backend.db.iris_client import MemoryIRISClient, NativeIRISClient


class _FailingNode:
    def get(self, _key, _default_value):
        raise RuntimeError("<PROTECT> *Resource %Native_GlobalAccess required")


class _PassingNode:
    def get(self, _key, _default_value):
        return "MEDSENT"


class _JsonNode:
    def __init__(self, payload):
        self.payload = payload

    def get(self, _key, _default_value):
        return self.payload


class _StubIRIS:
    def __init__(self, node):
        self._node = node

    def node(self, _global_name):
        return self._node


def test_native_client_explains_missing_global_access():
    client = NativeIRISClient.__new__(NativeIRISClient)
    client._iris = _StubIRIS(_FailingNode())

    with pytest.raises(RuntimeError, match="Re-run the MedSim IRIS bootstrap"):
        client._verify_native_global_access()


def test_native_client_accepts_global_access():
    client = NativeIRISClient.__new__(NativeIRISClient)
    client._iris = _StubIRIS(_PassingNode())

    client._verify_native_global_access()


def test_native_client_load_json_uses_sdk_default_argument():
    client = NativeIRISClient.__new__(NativeIRISClient)
    client._iris = _StubIRIS(_JsonNode(json.dumps({"status": "ready"})))

    assert client._load_json("MedSim.WorldModel", "model_demo") == {"status": "ready"}


def test_memory_client_write_world_model_builds_spatial_bundle():
    client = MemoryIRISClient()
    model = client.create_or_replace_model("fac_demo", status="queued")

    ready = client.write_world_model(
        "fac_demo",
        {
            "world_id": "world_bundle_test",
            "splat_url": "facilities/fac_demo/models/world_bundle_test/scene.spz",
            "scene_manifest": {
                "units": [
                    {
                        "unit_id": "unit_1",
                        "rooms": [
                            {
                                "room_id": "R101",
                                "type": "patient_room",
                                "grid_col": 1,
                                "grid_row": 2,
                                "adjacency": [],
                                "equipment": [
                                    {
                                        "type": "call_light",
                                        "position": "bed rail",
                                        "accessible": True,
                                        "confidence": 0.9,
                                    }
                                ],
                            }
                        ],
                    }
                ],
                "flow_annotations": {},
            },
            "source_image_count": 8,
            "caption": "Bundle test",
        },
        model_id=model.model_id,
    )

    assert ready.spatial_bundle_json["unit_id"] == "unit_1"
    assert len(ready.spatial_bundle_json["rooms"]) == 1
    assert ready.spatial_bundle_json["rooms"][0]["room_id"] == "R101"
