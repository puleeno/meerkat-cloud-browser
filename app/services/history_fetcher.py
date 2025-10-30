from typing import Dict, List
import threading
import requests
import json


def _requests_fetch(years: List[int], cookies: List[dict], headers: Dict[str, str] | None):
	results: Dict[int, int] = {}
	raw_map: Dict[int, str] = {}
	cookie_header = "; ".join([f"{c['name']}={c.get('value','')}" for c in cookies if c.get('name')])
	session = requests.Session()
	for y in years:
		url = f"https://www.rei.com/order-details/rs/purchase-details/history?year={y}"
		hs = dict(headers or {})
		if cookie_header:
			hs["Cookie"] = cookie_header
		try:
			r = session.get(url, headers=hs, timeout=20)
			r.raise_for_status()
			raw = r.text
			data = r.json()
			history = data.get("history") or []
			results[int(y)] = int(len(history))
			raw_map[int(y)] = raw
		except Exception:
			results[int(y)] = 0
			raw_map[int(y)] = ""
	return results, raw_map


def fetch_orders_per_year_with_scrapy(years: List[int], cookies: List[dict], headers: Dict[str, str] | None = None):
	# Nếu không ở main thread (dashboard/CLI nền), tránh Scrapy/Twisted signal -> dùng requests
	if threading.current_thread() is not threading.main_thread():
		return _requests_fetch(years, cookies, headers)

	try:
		from scrapy.crawler import CrawlerProcess  # lazy import
		from scrapy import signals
		from ..spiders.rei_history import ReiHistorySpider  # lazy import
	except Exception:
		# Fallback requests nếu Scrapy không sẵn sàng
		return _requests_fetch(years, cookies, headers)

	results: Dict[int, int] = {}
	raw_map: Dict[int, str] = {}

	process = CrawlerProcess(settings={
		"LOG_LEVEL": "ERROR",
		"USER_AGENT": headers.get("User-Agent") if headers else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
	})

	def collect(item):
		y = int(item.get("year"))
		count = int(item.get("orders_count", 0))
		results[y] = count
		raw_map[y] = item.get("raw_json", "")

	crawler = process.create_crawler(ReiHistorySpider)
	crawler.signals.connect(collect, signal=signals.item_scraped)
	process.crawl(crawler, years=years, cookies=cookies, headers=headers or {})
	process.start()
	return results, raw_map
