import asyncio
import json

from backend.db.redis_client import IRISPubSub


class _StubIRIS:
    def __init__(self) -> None:
        self.increment_calls: list[tuple[object, ...]] = []
        self.set_calls: list[tuple[object, ...]] = []

    def increment(self, *args):
        self.increment_calls.append(args)
        return 7

    def set(self, *args):
        self.set_calls.append(args)


def test_iris_pubsub_publish_uses_increment_amount_first():
    stub = _StubIRIS()
    pubsub = IRISPubSub()
    pubsub._iris = stub

    asyncio.run(pubsub.publish("scan:unit_1", {"type": "status", "status": "running"}))

    assert stub.increment_calls == [(1, "MedSentinel.EventQueue", "scan:unit_1", "counter")]
    encoded = json.dumps({"type": "status", "status": "running"})
    assert stub.set_calls == [(encoded, "MedSentinel.EventQueue", "scan:unit_1", "events", 7)]
