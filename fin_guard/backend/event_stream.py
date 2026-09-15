"""Kafka market event transport with an explicit local fallback."""

from __future__ import annotations

import asyncio
import json
from collections import deque
from typing import Any


class InMemoryEventBus:
    def __init__(self):
        self.events: deque[dict[str, Any]] = deque()

    async def publish(self, event: dict[str, Any]) -> None:
        self.events.append(event)

    async def consume(self) -> dict[str, Any] | None:
        return self.events.popleft() if self.events else None


class KafkaEventBus:
    """AIOKafka transport; broker connections are created lazily."""

    def __init__(self, bootstrap_servers: str = "localhost:9092", topic: str = "finguard.market.ticks"):
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.producer = None
        self.consumer = None

    async def publish(self, event: dict[str, Any]) -> None:
        from aiokafka import AIOKafkaProducer
        if self.producer is None:
            self.producer = AIOKafkaProducer(bootstrap_servers=self.bootstrap_servers)
            await self.producer.start()
        await self.producer.send_and_wait(self.topic, json.dumps(event).encode("utf-8"))

    async def consume(self):
        from aiokafka import AIOKafkaConsumer
        if self.consumer is None:
            self.consumer = AIOKafkaConsumer(self.topic, bootstrap_servers=self.bootstrap_servers, auto_offset_reset="latest")
            await self.consumer.start()
        message = await self.consumer.getone()
        return json.loads(message.value.decode("utf-8"))


async def publish_market_event(event: dict[str, Any], bus: KafkaEventBus | InMemoryEventBus | None = None) -> str:
    """Publish to Kafka, falling back to an in-process queue when unavailable."""
    transport = bus or KafkaEventBus()
    try:
        await transport.publish(event)
        return "kafka" if isinstance(transport, KafkaEventBus) else "memory"
    except Exception:
        fallback = InMemoryEventBus()
        await fallback.publish(event)
        return "memory_fallback"