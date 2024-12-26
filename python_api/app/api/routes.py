from fastapi import APIRouter, HTTPException
from typing import Optional, Dict
from pydantic import BaseModel
from app.browser.controller import BrowserController
from app.browser.network_interceptor import RequestFilter

router = APIRouter()

class UrlRequest(BaseModel):
    url: str

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