import json

import pytest

from backend.db.iris_client import NativeIRISClient


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
