from geckordp.actors.root import RootActor
from geckordp.firefox import Firefox
from geckordp.profile import ProfileManager
from geckordp.rdp_client import RDPClient
from geckordp.actors.screenshot import ScreenshotActor

from app.utils.logger import BrowserLogger
from app.browser.performance import PerformanceMonitor
from app.browser.cache_manager import CacheManager
from app.browser.proxy_config import ProxyManager

from typing import Optional, Dict, Any
from datetime import datetime
import asyncio
from pathlib import Path


class BrowserController:
    _instance: Optional['BrowserController'] = None

    def __init__(self):
        self.firefox: Optional[Firefox] = None
        self.client: Optional[RDPClient] = None
        self.is_running = False
        self.tabs = {}
        self.root = None

        # Initialize new components
        self.logger = BrowserLogger(Path("logs"))
        self.performance_monitor = PerformanceMonitor(self)
        self.cache_manager = CacheManager(self)
        self.proxy_manager = ProxyManager(self)

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
            client.connect("127.0.0.1", port)

            self.client = client
            self.is_running = True

            # initialize root
            root = RootActor(client)

            self.root = root

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
            screenshot_actor = ScreenshotActor(self.client, self.root["screenshotActor"])

            browsing_context_id = actor_ids["browsingContextID"]

            responseImg = screenshot_actor.capture(
                browsing_context_id=browsing_context_id,
                copy_clipboard=False,
                dpr=2,
                delay_sec=0,
            )

            value = responseImg.get("value", None)

            response = await self.client.send_packet({
                "to": "root",
                "type": "captureScreenshot"
            })
            return response.get("data", value)
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

    async def create_tab(self, url: str = "about:blank") -> Dict[str, Any]:
        try:
            response = await self.client.send_packet({
                "to": "root",
                "type": "createTab",
                "url": url
            })
            tab_id = response.get("tab_id")
            self.tabs[tab_id] = {"url": url, "created_at": datetime.now()}
            return {"tab_id": tab_id, "status": "created"}
        except Exception as e:
            print(f"Error creating tab: {e}")
            return {}

    async def switch_tab(self, tab_id: str) -> bool:
        try:
            await self.client.send_packet({
                "to": "root",
                "type": "switchTab",
                "tab_id": tab_id
            })
            return True
        except Exception as e:
            print(f"Error switching tab: {e}")
            return False

    async def close_tab(self, tab_id: str) -> bool:
        try:
            await self.client.send_packet({
                "to": "root",
                "type": "closeTab",
                "tab_id": tab_id
            })
            self.tabs.pop(tab_id, None)
            return True
        except Exception as e:
            print(f"Error closing tab: {e}")
            return False

    async def get_browser_status(self) -> Dict:
        """Get comprehensive browser status"""
        if not self.is_running:
            return {"status": "stopped"}
            
        try:
            metrics = await self.performance_monitor.collect_metrics()
            cache_size = await self.cache_manager.get_cache_size()
            
            return {
                "status": "running",
                "tabs": len(self.tabs),
                "performance": metrics.__dict__,
                "cache_size": cache_size,
                "proxy": self.proxy_manager.current_settings.__dict__ if self.proxy_manager.current_settings else None
            }
        except Exception as e:
            self.logger.error.error(f"Error getting browser status: {e}")
            return {"status": "error", "message": str(e)}