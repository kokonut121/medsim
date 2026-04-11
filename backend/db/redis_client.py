from __future__ import annotations

"""
Redis pub/sub wrapper for real-time scan and simulation events.

Uses ``redis.asyncio`` under the hood. The public surface is kept
intentionally narrow so call sites (websocket endpoints, scenario runner,
agent orchestrator) don't need to know about pubsub objects or connection
pools:

  - ``await publish(channel, payload)`` — JSON-encode and PUBLISH
  - ``await subscribe(channel)`` — returns an ``asyncio.Queue`` that a
    background task fills with decoded payloads
  - ``unsubscribe(channel, queue)`` — sync; cancels the pump and schedules
    async pubsub teardown

Connection details come from ``backend.config.Settings`` (``redis_url`` and
optional ``redis_password``). The client is lazily constructed on first use
so importing this module does not require a running event loop.
"""

import asyncio
import json
import logging
from typing import Any

import redis.asyncio as aioredis
from redis.asyncio.client import PubSub

from backend.config import get_settings

logger = logging.getLogger(__name__)


class RedisPubSub:
    def __init__(self) -> None:
        self._redis: aioredis.Redis | None = None
        # Map queue identity -> (pubsub handle, pump task) so unsubscribe can
        # tear down the right subscription when given only the queue.
        self._subscriptions: dict[int, tuple[PubSub, asyncio.Task[None]]] = {}

    async def _client(self) -> aioredis.Redis:
        if self._redis is None:
            settings = get_settings()
            kwargs: dict[str, Any] = {"decode_responses": True}
            if settings.redis_password:
                kwargs["password"] = settings.redis_password
            self._redis = aioredis.from_url(settings.redis_url, **kwargs)
        return self._redis

    async def publish(self, channel: str, payload: Any) -> None:
        """Best-effort publish. Live-feed semantics: log but don't abort the
        caller if Redis is momentarily unreachable."""
        try:
            client = await self._client()
            await client.publish(channel, json.dumps(payload, default=str))
        except Exception:
            logger.exception("redis publish failed for channel %s", channel)

    async def subscribe(self, channel: str) -> asyncio.Queue[Any]:
        """Subscribe to ``channel`` and return an ``asyncio.Queue`` that a
        background task fills with JSON-decoded message payloads."""
        client = await self._client()
        pubsub = client.pubsub()
        await pubsub.subscribe(channel)
        queue: asyncio.Queue[Any] = asyncio.Queue()

        async def _pump() -> None:
            try:
                async for message in pubsub.listen():
                    if not message or message.get("type") != "message":
                        continue
                    data = message.get("data")
                    if isinstance(data, (bytes, bytearray)):
                        data = data.decode("utf-8")
                    if isinstance(data, str):
                        try:
                            payload = json.loads(data)
                        except json.JSONDecodeError:
                            payload = data
                    else:
                        payload = data
                    await queue.put(payload)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("redis pubsub pump crashed for channel %s", channel)

        task = asyncio.create_task(_pump(), name=f"redis-pubsub:{channel}")
        self._subscriptions[id(queue)] = (pubsub, task)
        return queue

    def unsubscribe(self, channel: str, queue: asyncio.Queue[Any]) -> None:
        """Sync teardown. Cancels the pump task and schedules async cleanup
        of the underlying pubsub handle (unsubscribe + close)."""
        entry = self._subscriptions.pop(id(queue), None)
        if entry is None:
            return
        pubsub, task = entry
        task.cancel()
        try:
            asyncio.create_task(
                self._close_pubsub(pubsub, channel),
                name=f"redis-pubsub-close:{channel}",
            )
        except RuntimeError:
            # No running loop (e.g., called during shutdown). The pubsub
            # handle will be garbage-collected with the client.
            pass

    async def _close_pubsub(self, pubsub: PubSub, channel: str) -> None:
        try:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
        except Exception:
            logger.exception("redis pubsub cleanup failed for channel %s", channel)

    async def close(self) -> None:
        """Close the shared client. Intended for application shutdown."""
        if self._redis is not None:
            try:
                await self._redis.close()
            finally:
                self._redis = None


redis_client = RedisPubSub()
