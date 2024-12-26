from enum import Enum
from typing import Dict, Set, Callable
import asyncio

class BrowserEvent(Enum):
    PAGE_LOAD = "page_load"
    CONSOLE_MESSAGE = "console_message"
    NETWORK_REQUEST = "network_request"
    DOWNLOAD_STARTED = "download_started"
    ERROR = "error"

class EventSystem:
    def __init__(self):
        self.listeners: Dict[BrowserEvent, Set[Callable]] = {
            event: set() for event in BrowserEvent
        }
        self.event_queue = asyncio.Queue()
        
    def add_listener(self, event: BrowserEvent, callback: Callable):
        self.listeners[event].add(callback)
        
    def remove_listener(self, event: BrowserEvent, callback: Callable):
        self.listeners[event].discard(callback)
        
    async def emit(self, event: BrowserEvent, data: Dict):
        await self.event_queue.put((event, data))
        
    async def process_events(self):
        while True:
            event, data = await self.event_queue.get()
            for callback in self.listeners[event]:
                try:
                    await callback(data)
                except Exception as e:
                    print(f"Error in event callback: {e}") 