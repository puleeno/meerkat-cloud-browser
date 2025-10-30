import json
import scrapy
from typing import Iterable, List


class ReiHistorySpider(scrapy.Spider):
	name = "rei_history"

	custom_settings = {
		"LOG_LEVEL": "ERROR",
	}

	def __init__(self, years: List[int] | None = None, cookies: List[dict] | None = None, headers: dict | None = None, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.years = years or []
		self.cookies = cookies or []
		self.headers = headers or {}

	def start_requests(self) -> Iterable[scrapy.Request]:
		cookie_dict = {c["name"]: c.get("value", "") for c in self.cookies if c.get("name") and c.get("value")}
		for y in self.years:
			url = f"https://www.rei.com/order-details/rs/purchase-details/history?year={y}"
			yield scrapy.Request(
				url,
				cookies=cookie_dict,
				headers=self.headers,
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
