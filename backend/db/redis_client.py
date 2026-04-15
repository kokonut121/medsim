from __future__ import annotations

"""
Live event pub/sub for swarm simulation and scan streams.

Two backends share a common queue-based API:

- ``InMemoryPubSub`` — asyncio-queue fan-out inside a single process. Dev
  default and the fallback when IRIS is unreachable.
- ``IRISPubSub`` — IRIS-backed append-only event log. One global per channel:
    ^MedSentinel.EventQueue(channel, "counter")       -> int sequence
    ^MedSentinel.EventQueue(channel, "events", seq)   -> JSON payload
  Publishers atomically ``$INCREMENT`` the counter and write the payload at
  that sequence. Subscribers read the current counter, spawn a poll task,
  and drain ``(cursor, latest]`` into an ``asyncio.Queue`` at a fixed
  interval. Chosen automatically when ``MEDSENTINEL_IRIS_MODE=native``.

Call sites (``backend.api.simulate``, ``backend.api.websocket``,
``backend.simulation.scenario_runner``, ``backend.agents.orchestrator``)
import ``redis_client`` and are agnostic to the backend.
"""

import asyncio
import json
import logging
from collections import defaultdict
from typing import Any, Callable

from backend.config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# In-memory backend (default / fallback)
# ---------------------------------------------------------------------------


class InMemoryPubSub:
    def __init__(self) -> None:
        self.channels: dict[str, list[asyncio.Queue[Any]]] = defaultdict(list)

    async def publish(self, channel: str, payload: Any) -> None:
        for queue in self.channels[channel]:
            await queue.put(payload)

    async def subscribe(self, channel: str) -> asyncio.Queue[Any]:
        queue: asyncio.Queue[Any] = asyncio.Queue()
        self.channels[channel].append(queue)
        return queue

    def unsubscribe(self, channel: str, queue: asyncio.Queue[Any]) -> None:
        self.channels[channel] = [q for q in self.channels[channel] if q is not queue]


# ---------------------------------------------------------------------------
# IRIS backend
# ---------------------------------------------------------------------------


class IRISPubSub:
    GLOBAL = "MedSentinel.EventQueue"
    POLL_INTERVAL_S = 0.05  # 50 ms — fast enough for live graph streaming

    def __init__(self) -> None:
        self._iris: Any = None
        self._connection: Any = None
        # Serializes access to the shared IRIS connection across async tasks,
        # since the native Python client is not thread-safe on a single
        # connection.
        self._lock = asyncio.Lock()
        self._subscriptions: dict[int, asyncio.Task[None]] = {}

    def _ensure_client(self) -> Any:
        if self._iris is not None:
            return self._iris
        import iris  # type: ignore

        settings = get_settings()
        self._connection = iris.connect(
            hostname=settings.iris_host,
            port=settings.iris_port,
            namespace=settings.iris_namespace,
            username=settings.iris_user,
            password=settings.iris_password,
            timeout=settings.iris_connect_timeout_ms,
        )
        self._iris = iris.createIRIS(self._connection)
        return self._iris

    async def _run_locked(self, fn: Callable[[], Any]) -> Any:
        async with self._lock:
            return await asyncio.to_thread(fn)

    async def publish(self, channel: str, payload: Any) -> None:
        encoded = json.dumps(payload, default=str)

        def _do_publish() -> None:
            try:
                client = self._ensure_client()
                # $INCREMENT is atomic and returns the new value. Write the
                # payload AFTER the increment so subscribers can defensively
                # detect in-flight writes by a missing node at ``seq``.
                seq = client.increment(1, self.GLOBAL, channel, "counter")
                client.set(encoded, self.GLOBAL, channel, "events", seq)
            except Exception:
                logger.exception("IRIS publish failed for channel %s", channel)

        await self._run_locked(_do_publish)

    async def subscribe(self, channel: str) -> asyncio.Queue[Any]:
        queue: asyncio.Queue[Any] = asyncio.Queue()

        def _read_counter() -> int:
            try:
                client = self._ensure_client()
                value = client.get(self.GLOBAL, channel, "counter")
                return int(value) if value is not None else 0
            except Exception:
                logger.exception("IRIS counter read failed for channel %s", channel)
                return 0

        start_seq = await self._run_locked(_read_counter)

        async def _pump() -> None:
            cursor = start_seq
            try:
                while True:
                    from_seq = cursor

                    def _fetch() -> tuple[int, list[tuple[int, Any]]]:
                        try:
                            client = self._ensure_client()
                            latest_raw = client.get(self.GLOBAL, channel, "counter")
                            latest = int(latest_raw) if latest_raw is not None else 0
                            batch: list[tuple[int, Any]] = []
                            max_seen = from_seq
                            for seq in range(from_seq + 1, latest + 1):
                                raw = client.get(self.GLOBAL, channel, "events", seq)
                                if raw is None:
                                    # Publisher has incremented the counter but
                                    # not yet written the payload. Stop here
                                    # and re-poll; we'll pick it up next round
                                    # without skipping past it.
                                    break
                                try:
                                    batch.append((seq, json.loads(raw)))
                                except json.JSONDecodeError:
                                    batch.append((seq, raw))
                                max_seen = seq
                            return max_seen, batch
                        except Exception:
                            logger.exception("IRIS pump fetch failed for channel %s", channel)
                            return from_seq, []

                    new_cursor, batch = await self._run_locked(_fetch)
                    for _seq, payload in batch:
                        await queue.put(payload)
                    cursor = new_cursor
                    await asyncio.sleep(self.POLL_INTERVAL_S)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("IRIS pump crashed for channel %s", channel)

        task = asyncio.create_task(_pump(), name=f"iris-pubsub:{channel}")
        self._subscriptions[id(queue)] = task
        return queue

    def unsubscribe(self, channel: str, queue: asyncio.Queue[Any]) -> None:
        task = self._subscriptions.pop(id(queue), None)
        if task is not None:
            task.cancel()


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------


def _create_pubsub() -> InMemoryPubSub | IRISPubSub:
    settings = get_settings()
    if settings.iris_mode == "native":
        try:
            return IRISPubSub()
        except Exception:
            logger.exception("Falling back to in-memory pub/sub after IRIS init failure")
    return InMemoryPubSub()


redis_client = _create_pubsub()
