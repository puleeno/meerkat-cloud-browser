from typing import Optional, List

class CacheManager:
    def __init__(self, controller):
        self.controller = controller
        
    async def clear_cache(self, domain: Optional[str] = None):
        await self.controller.client.send_packet({
            "to": "root",
            "type": "clearCache",
            "domain": domain
        })
        
    async def get_cache_size(self) -> int:
        response = await self.controller.client.send_packet({
            "to": "root",
            "type": "getCacheSize"
        })
        return response.get('size', 0)
        
    async def get_cached_resources(self, domain: Optional[str] = None) -> List[str]:
        response = await self.controller.client.send_packet({
            "to": "root",
            "type": "getCachedResources",
            "domain": domain
        })
        return response.get('resources', []) 