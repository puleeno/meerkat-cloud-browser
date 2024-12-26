from dataclasses import dataclass
from typing import Optional, Dict, List, Callable
import asyncio

@dataclass
class RequestFilter:
    url_pattern: str
    resource_type: Optional[str] = None
    method: Optional[str] = None

class NetworkInterceptor:
    def __init__(self, controller):
        self.controller = controller
        self.filters: List[RequestFilter] = []
        self.callbacks: Dict[str, Callable] = {}

    async def add_filter(self, filter: RequestFilter, callback: Callable):
        filter_id = str(len(self.filters))
        self.filters.append(filter)
        self.callbacks[filter_id] = callback
        
        await self.controller.client.send_packet({
            "to": "root",
            "type": "setRequestInterception",
            "patterns": [{"urlPattern": filter.url_pattern}]
        })
        
        return filter_id

    async def handle_request(self, request_data: Dict):
        for i, filter in enumerate(self.filters):
            if self._matches_filter(request_data, filter):
                callback = self.callbacks.get(str(i))
                if callback:
                    modified_request = await callback(request_data)
                    return modified_request
        return request_data

    def _matches_filter(self, request: Dict, filter: RequestFilter) -> bool:
        if not request["url"].match(filter.url_pattern):
            return False
        if filter.resource_type and request.get("resourceType") != filter.resource_type:
            return False
        if filter.method and request.get("method") != filter.method:
            return False
        return True 