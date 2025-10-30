from typing import Dict, List
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from ..spiders.rei_history import ReiHistorySpider


def fetch_orders_per_year_with_scrapy(years: List[int], cookies: List[dict]) -> Dict[int, int]:
	results: Dict[int, int] = {}

	process = CrawlerProcess(settings={
		"LOG_LEVEL": "ERROR",
		"USER_AGENT": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
	})

	def collect(item):
		y = int(item.get("year"))
		count = int(item.get("orders_count", 0))
		results[y] = count

	process.crawl(ReiHistorySpider, years=years, cookies=cookies)
	for crawler in process.crawlers:
		crawler.signals.connect(collect, signal=crawler.signals.item_scraped)
	process.start()  # runs to completion
	return results
