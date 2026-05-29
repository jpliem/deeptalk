import asyncio
from deeptalk.bus import EventBus


async def test_subscriber_receives_published_item():
    bus = EventBus()
    q = bus.subscribe()
    await bus.publish("hello")
    assert await asyncio.wait_for(q.get(), timeout=1.0) == "hello"


async def test_two_subscribers_each_receive_item():
    bus = EventBus()
    q1 = bus.subscribe()
    q2 = bus.subscribe()
    await bus.publish(42)
    assert await asyncio.wait_for(q1.get(), timeout=1.0) == 42
    assert await asyncio.wait_for(q2.get(), timeout=1.0) == 42


async def test_unsubscribed_queue_gets_nothing():
    bus = EventBus()
    q = bus.subscribe()
    bus.unsubscribe(q)
    await bus.publish("x")
    assert q.empty()
