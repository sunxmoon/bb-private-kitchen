import asyncio
from typing import Set


class Broadcaster:
    def __init__(self):
        self.queues: Set[asyncio.Queue] = set()
        self.loop = None

    async def subscribe(self):
        q = asyncio.Queue()
        self.queues.add(q)
        if self.loop is None:
            self.loop = asyncio.get_running_loop()
        try:
            while True:
                msg = await q.get()
                yield f"data: {msg}\n\n"
        finally:
            self.queues.discard(q)

    def broadcast(self, message: str):
        if self.loop and not self.loop.is_closed():
            self.loop.call_soon_threadsafe(self._broadcast_in_loop, message)

    def _broadcast_in_loop(self, message: str):
        for q in self.queues:
            q.put_nowait(message)


order_broadcaster = Broadcaster()
