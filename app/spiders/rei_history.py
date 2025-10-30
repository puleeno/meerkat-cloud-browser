import json
import scrapy
from typing import Iterable, List


class ReiHistorySpider(scrapy.Spider):
	name = "rei_history"

	custom_settings = {
		"LOG_LEVEL": "ERROR",
	}

	def __init__(self, years: List[int] | None = None, cookies: List[dict] | None = None, headers: dict | None = None, proxy: str | None = None, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.years = years or []
		self.cookies = cookies or []
		self.headers = headers or {}
		self.proxy = proxy

	def start_requests(self) -> Iterable[scrapy.Request]:
		cookie_dict = {c["name"]: c.get("value", "") for c in self.cookies if c.get("name") and c.get("value")}
		for y in self.years:
			url = f"https://www.rei.com/order-details/rs/purchase-details/history?year={y}"
			meta = {}
			if self.proxy:
				meta["proxy"] = self.proxy
			yield scrapy.Request(
				url,
				cookies=cookie_dict,
				headers=self.headers,
				callback=self.parse_history,
				cb_kwargs={"year": y},
				meta=meta,
			)

	def parse_history(self, response: scrapy.http.Response, year: int):
		raw = response.text
		try:
			data = json.loads(raw)
			history = data.get("history") or []
			orders_count = int(len(history))
		except Exception:
			orders_count = 0
		yield {"year": year, "orders_count": orders_count, "raw_json": raw}
