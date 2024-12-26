from dataclasses import dataclass
from typing import Optional, Dict, List

@dataclass
class ProxySettings:
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    bypass_list: Optional[List[str]] = None

class ProxyManager:
    def __init__(self, controller):
        self.controller = controller
        self.current_settings: Optional[ProxySettings] = None
        
    async def set_proxy(self, settings: ProxySettings) -> bool:
        try:
            await self.controller.client.send_packet({
                "to": "root",
                "type": "setProxy",
                "settings": {
                    "host": settings.host,
                    "port": settings.port,
                    "username": settings.username,
                    "password": settings.password,
                    "bypassList": settings.bypass_list
                }
            })
            self.current_settings = settings
            return True
        except Exception as e:
            print(f"Error setting proxy: {e}")
            return False
            
    async def disable_proxy(self) -> bool:
        try:
            await self.controller.client.send_packet({
                "to": "root",
                "type": "disableProxy"
            })
            self.current_settings = None
            return True
        except Exception as e:
            print(f"Error disabling proxy: {e}")
            return False 