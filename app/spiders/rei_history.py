import json
import scrapy
from typing import Dict, Iterable, List


class ReiHistorySpider(scrapy.Spider):
	name = "rei_history"

	custom_settings = {
		"LOG_LEVEL": "ERROR",
	}

	def __init__(self, years: List[int] | None = None, cookies: List[dict] | None = None, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.years = years or []
		self.cookies = cookies or []

	def start_requests(self) -> Iterable[scrapy.Request]:
		for y in self.years:
			url = f"https://www.rei.com/order-details/rs/purchase-details/history?year={y}"
			yield scrapy.Request(
				url,
				cookies={c["name"]: c.get("value", "") for c in self.cookies if c.get("name") and c.get("value")},
				callback=self.parse_history,
				cb_kwargs={"year": y},
			)

	def parse_history(self, response: scrapy.http.Response, year: int):
		try:
			data = json.loads(response.text)
			history = data.get("history") or []
			yield {"year": year, "orders_count": int(len(history))}
		except Exception:
			yield {"year": year, "orders_count": 0}
