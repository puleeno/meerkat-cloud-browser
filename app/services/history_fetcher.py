from typing import Dict, List


def fetch_orders_per_year_with_scrapy(years: List[int], cookies: List[dict], headers: Dict[str, str] | None = None) -> Dict[int, int]:
	try:
		from scrapy.crawler import CrawlerProcess  # lazy import
		from scrapy import signals
		from ..spiders.rei_history import ReiHistorySpider  # lazy import
	except Exception:
		return {}

	results: Dict[int, int] = {}

	process = CrawlerProcess(settings={
		"LOG_LEVEL": "ERROR",
		"USER_AGENT": headers.get("User-Agent") if headers else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
	})

	def collect(item):
		y = int(item.get("year"))
		count = int(item.get("orders_count", 0))
		results[y] = count

	crawler = process.create_crawler(ReiHistorySpider)
	crawler.signals.connect(collect, signal=signals.item_scraped)
	process.crawl(crawler, years=years, cookies=cookies, headers=headers or {})
	process.start()
	return results
