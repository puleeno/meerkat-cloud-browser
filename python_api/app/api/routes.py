from fastapi import APIRouter, HTTPException
from typing import Optional, Dict
from pydantic import BaseModel
from app.browser.controller import BrowserController
from app.browser.network_interceptor import RequestFilter
from app.browser.proxy_config import ProxySettings

router = APIRouter()

class UrlRequest(BaseModel):
    url: str

class TabRequest(BaseModel):
    tab_id: str  # Unique identifier for the tab
    action: str  # Action to perform on the tab (e.g., "close", "refresh")

class DownloadRequest(BaseModel):
    url: str  # URL of the file to download
    destination: str

class JavaScriptRequest(BaseModel):
    script: str

@router.post("/start")
async def start_browser():
    controller = BrowserController.get_instance()
    success = await controller.start()
    if not success:
        raise HTTPException(status_code=500, detail="Failed to start browser")
    return {"status": "Browser started successfully"}

@router.post("/navigate")
async def navigate_browser(request: UrlRequest):
    controller = BrowserController.get_instance()
    success = await controller.navigate(request.url)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to navigate")
    return {"status": f"Navigated to {request.url}"}

@router.post("/stop")
async def stop_browser():
    controller = BrowserController.get_instance()
    success = await controller.stop()
    if not success:
        raise HTTPException(status_code=500, detail="Failed to stop browser")
    return {"status": "Browser stopped successfully"}

@router.get("/screenshot")
async def take_screenshot():
    controller = BrowserController.get_instance()
    screenshot = await controller.take_screenshot()
    if not screenshot:
        raise HTTPException(status_code=500, detail="Failed to take screenshot")
    return {"screenshot": screenshot}

@router.post("/execute")
async def execute_javascript(request: JavaScriptRequest):
    controller = BrowserController.get_instance()
    result = await controller.execute_js(request.script)
    if result is None:
        raise HTTPException(status_code=500, detail="Failed to execute JavaScript")
    return {"result": result}


@router.post("/tab")
async def create_tab(request: TabRequest):
    controller = BrowserController.get_instance()
    result = await controller.create_tab(request.url)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to create tab")
    return result

@router.post("/network/intercept")
async def add_network_filter(filter: RequestFilter):
    controller = BrowserController.get_instance()
    filter_id = await controller.network_interceptor.add_filter(
        filter,
        lambda req: req  # Default pass-through callback
    )
    return {"filter_id": filter_id}

@router.post("/download")
async def start_download(request: DownloadRequest):
    controller = BrowserController.get_instance()
    download_id = await controller.download_manager.start_download(
        request.url,
        request.filename
    )
    return {"download_id": download_id}

@router.get("/download/{download_id}")
async def get_download_status(download_id: str):
    controller = BrowserController.get_instance()
    status = controller.download_manager.downloads.get(download_id)
    if not status:
        raise HTTPException(status_code=404, detail="Download not found")
    return status

@router.get("/status")
async def get_status():
    controller = BrowserController.get_instance()
    return await controller.get_browser_status()

@router.get("/performance")
async def get_performance():
    controller = BrowserController.get_instance()
    metrics = await controller.performance_monitor.collect_metrics()
    return metrics.__dict__

@router.post("/cache/clear")
async def clear_cache(domain: Optional[str] = None):
    controller = BrowserController.get_instance()
    await controller.cache_manager.clear_cache(domain)
    return {"status": "Cache cleared"}

@router.post("/proxy")
async def set_proxy(settings: ProxySettings):
    controller = BrowserController.get_instance()
    success = await controller.proxy_manager.set_proxy(settings)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to set proxy")
    return {"status": "Proxy configured"}

@router.delete("/proxy")
async def disable_proxy():
    controller = BrowserController.get_instance()
    success = await controller.proxy_manager.disable_proxy()
    if not success:
        raise HTTPException(status_code=500, detail="Failed to disable proxy")
    return {"status": "Proxy disabled"}