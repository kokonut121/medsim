from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any


class RedisPubSub:
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
        self.channels[channel] = [item for item in self.channels[channel] if item is not queue]


redis_client = RedisPubSub()

