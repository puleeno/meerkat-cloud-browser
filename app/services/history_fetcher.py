from typing import Dict, List


def fetch_orders_per_year_with_scrapy(years: List[int], cookies: List[dict]) -> Dict[int, int]:
	try:
		from scrapy.crawler import CrawlerProcess  # lazy import
		from ..spiders.rei_history import ReiHistorySpider  # lazy import
	except Exception:
		# Scrapy chưa được cài hoặc môi trường thiếu dependency; trả về rỗng để app không lỗi
		return {}

	results: Dict[int, int] = {}

	process = CrawlerProcess(settings={
		"LOG_LEVEL": "ERROR",
		"USER_AGENT": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
	})

	def collect(item):
		y = int(item.get("year"))
		count = int(item.get("orders_count", 0))
		results[y] = count

	crawler = process.create_crawler(ReiHistorySpider)
	crawler.signals.connect(collect, signal=crawler.signals.item_scraped)
	process.crawl(crawler, years=years, cookies=cookies)
	process.start()
	return results
