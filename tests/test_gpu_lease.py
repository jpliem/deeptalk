import asyncio

from deeptalk.gpu.lease import GpuLease


async def test_lease_serializes_holders():
    lease = GpuLease()
    active = 0
    max_seen = 0

    async def worker():
        nonlocal active, max_seen
        async with lease.hold():
            active += 1
            max_seen = max(max_seen, active)
            await asyncio.sleep(0.01)
            active -= 1

    await asyncio.gather(*(worker() for _ in range(5)))
    assert max_seen == 1


async def test_lease_releases_on_exception():
    lease = GpuLease()
    with __import__("pytest").raises(RuntimeError):
        async with lease.hold():
            raise RuntimeError("boom")
    async with lease.hold():
        pass
