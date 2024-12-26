from pathlib import Path
from typing import Dict, Optional
import aiofiles
import asyncio

class DownloadManager:
    def __init__(self, download_dir: Path):
        self.download_dir = download_dir
        self.downloads: Dict[str, Dict] = {}
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
    async def start_download(self, url: str, filename: Optional[str] = None) -> str:
        download_id = str(len(self.downloads))
        self.downloads[download_id] = {
            "url": url,
            "filename": filename or url.split("/")[-1],
            "status": "starting",
            "progress": 0
        }
        
        asyncio.create_task(self._handle_download(download_id))
        return download_id
        
    async def _handle_download(self, download_id: str):
        download = self.downloads[download_id]
        try:
            # Start download using geckordp
            response = await self.controller.client.send_packet({
                "to": "root",
                "type": "downloadFile",
                "url": download["url"]
            })
            
            file_path = self.download_dir / download["filename"]
            async with aiofiles.open(file_path, 'wb') as f:
                while True:
                    chunk = await response.content.read(8192)
                    if not chunk:
                        break
                    await f.write(chunk)
                    
            self.downloads[download_id]["status"] = "completed"
            
        except Exception as e:
            self.downloads[download_id]["status"] = "failed"
            self.downloads[download_id]["error"] = str(e) 