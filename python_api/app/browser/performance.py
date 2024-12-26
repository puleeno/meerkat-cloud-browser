from dataclasses import dataclass
from typing import Dict, List
import time

@dataclass
class PerformanceMetrics:
    page_load_time: float
    memory_usage: float
    cpu_usage: float
    network_requests: int

class PerformanceMonitor:
    def __init__(self, controller):
        self.controller = controller
        self.metrics_history: List[Dict] = []
        
    async def collect_metrics(self) -> PerformanceMetrics:
        response = await self.controller.client.send_packet({
            "to": "root",
            "type": "getPerformanceMetrics"
        })
        
        metrics = PerformanceMetrics(
            page_load_time=response.get('pageLoadTime', 0),
            memory_usage=response.get('memoryUsage', 0),
            cpu_usage=response.get('cpuUsage', 0),
            network_requests=response.get('networkRequests', 0)
        )
        
        self.metrics_history.append({
            'timestamp': time.time(),
            'metrics': metrics
        })
        
        return metrics 