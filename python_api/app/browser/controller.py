from geckordp.actors.root import RootActor
from geckordp.firefox import Firefox
from geckordp.profile import ProfileManager
from geckordp.rdp_client import RDPClient

from typing import Optional, Dict, Any
from datetime import datetime
import asyncio

class BrowserController:
    _instance: Optional['BrowserController'] = None

    def __init__(self):
        self.firefox: Optional[Firefox] = None
        self.client: Optional[RDPClient] = None
        self.is_running = False
        self.tabs = {}

    @classmethod
    def get_instance(cls) -> 'BrowserController':
        if cls._instance is None:
            cls._instance = BrowserController()
        return cls._instance

    async def start(self) -> bool:
        if self.is_running:
            return False

        try:
            pm = ProfileManager()
            profile_name = "geckordp"
            port = 6000
            pm.clone("default-release", profile_name)
            profile = pm.get_profile_by_name(profile_name)
            profile.set_required_configs()

            self.firefox = Firefox()
            self.firefox.start("https://example.com/", port, profile_name)

            client = RDPClient()
            client.connect("localhost", port)

            self.client = client
            self.is_running = True

            # initialize root
            root = RootActor(client)

            # get a list of tabs
            self.tabs = root.list_tabs()

            return True
        except Exception as e:
            print(f"Error starting browser: {e}")
            return False

    async def navigate(self, url: str) -> bool:
        if not self.is_running or not self.client:
            return False

        try:
            await self.client.send_packet({
                "to": "root",
                "type": "navigateTo",
                "url": url
            })
            return True
        except Exception as e:
            print(f"Error navigating: {e}")
            return False

    async def stop(self) -> bool:
        if not self.is_running:
            return False

        try:
            if self.client:
                await self.client.close()
            if self.firefox:
                self.firefox.stop()
            self.is_running = False
            return True
        except Exception as e:
            print(f"Error stopping browser: {e}")
            return False

    async def take_screenshot(self) -> str:
        if not self.is_running or not self.client:
            return ""

        try:
            response = await self.client.send_packet({
                "to": "root",
                "type": "captureScreenshot"
            })
            return response.get("data", "")
        except Exception as e:
            print(f"Error taking screenshot: {e}")
            return ""

    async def execute_js(self, script: str) -> Any:
        if not self.is_running or not self.client:
            return None

        try:
            response = await self.client.send_packet({
                "to": "root",
                "type": "evaluateJavaScript",
                "script": script
            })
            return response.get("result")
        except Exception as e:
            print(f"Error executing JavaScript: {e}")
            return None