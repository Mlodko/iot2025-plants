from datetime import datetime, timedelta
from typing import Callable
import uuid
import asyncio

class ScheduledEvent:
    def __init__(self, time: datetime, action: Callable[[], None], repeat_interval: timedelta | None = None) -> None:
        self.id: uuid.UUID = uuid.uuid4()
        self.creation_time: datetime = datetime.now()
        self.execution_time: datetime = time
        self.action: Callable[[], None] = action
        self.repeat_interval: timedelta | None = repeat_interval
        self.executed: bool = False
        
    def execute(self) -> None:
        self.action()
        if self.repeat_interval:
            self.execution_time += self.repeat_interval
        else:
            self.executed = True
            
    def __lt__(self, other: 'ScheduledEvent') -> bool:
        return self.execution_time < other.execution_time
            
class Scheduler:
    def __init__(self) -> None:
        self.events: list[ScheduledEvent] = []
        self.queue_lock: asyncio.Lock = asyncio.Lock()
    
    async def add_event(self, event: ScheduledEvent) -> None:
        async with self.queue_lock:
            self.events.append(event)
            self.events.sort()
        
    async def remove_event(self, event_id: uuid.UUID) -> None:
        async with self.queue_lock:
            self.events = [event for event in self.events if event.id != event_id]
        
    async def run(self):
        while True:
            async with self.queue_lock:
                if not self.events:
                    event = None
                else:
                    event = self.events.pop(0)
            if not self.events:
                await asyncio.sleep(1)
                continue
            event = self.events.pop(0)
            await asyncio.sleep(max(0, (event.execution_time - datetime.now()).total_seconds()))
            event.execute()
            if not event.executed: #event is repeating, execution_time changed, sort the list again
                self.events.sort()