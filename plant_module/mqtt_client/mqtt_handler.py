"""Basically an interface that handlers should implement"""
from abc import ABC, abstractmethod


class MQTTHandler(ABC):
    @abstractmethod
    async def handle_message(self, topic: str, payload: bytes) -> None:
        pass