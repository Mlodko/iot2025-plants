import asyncio
from asyncio.tasks import Task
from uuid import UUID
from aiomqtt import Client
from abc import ABC, abstractmethod
from asyncio import Queue

"""Basically an interface that handlers should implement"""
class MQTTHandler(ABC):
    @abstractmethod
    async def handle_message(self, topic: str, payload: bytes) -> None:
        pass

'''This class is responsible for managing MQTT client connections and message dispatching to handlers.'''
class MQTTDispatcher:
    def __init__(self, pot_id: UUID, hostname: str, port: int=1883) -> None:
        self.client: Client = Client(hostname, port)
        self._running: bool = False
        self.handlers: dict[str, tuple[MQTTHandler, Queue[bytes]]] = {}
        self.tasks: dict[str, Task[None]] = {}
    
    """Start the dispatcher and subscribe to all topics"""
    async def start(self) -> None:
        # Subscribe to all topics
        for topic in self.handlers.keys():
            _ = await self.client.subscribe(topic)
        self._running = True
    
    '''Make sure to add handlers before starting the dispatcher'''
    def add_handler(self, topic: str, handler: MQTTHandler) -> None:
        if topic in self.handlers.keys():
            raise ValueError(f"Handler for topic {topic} already exists")
        
        queue: Queue[bytes] = Queue()
        self.handlers[topic] = (handler, queue)
        self.tasks[topic] = asyncio.create_task(self._process_queue(topic, handler, queue))      
    
    """Stop the dispatcher and unsubscribe from all topics"""
    async def stop(self) -> None:
        # unsubscribe from all topics
        for topic in self.handlers.keys():
            await self.client.unsubscribe(topic)
        self._running = False
    
    '''Run MQTT message loop, dispatch messages to handlers based on topic'''
    async def run_dispatch(self) -> None:
            all_topics: list[str] = [str(topic) for topic in self.handlers.keys()]
            async for message in self.client.messages:
                topic = str(message.topic)
                if topic not in all_topics:
                    print(f"[WARN] Received message for unknown topic: {topic}, skipping")
                    continue
                _, queue = self.handlers[topic]
                payload: bytes = message.payload if isinstance(message.payload, bytes) else bytes(str(message.payload), 'utf-8')
                await queue.put(payload)
            
    async def _process_queue(self, topic: str, handler: MQTTHandler, message_queue: Queue[bytes]) -> None:
        while self._running:
            payload: bytes = await message_queue.get()
            try:
                await handler.handle_message(topic, payload)
            except Exception as e:
                print(f"[ERROR] Error handling message for topic {topic}: {e}")
            message_queue.task_done()