import threading
import time
from datetime import datetime
from typing import Dict, List
import os
import random
import json

from flask import current_app

from ..extensions import db
from ..models import Account, AccountYearStat
from .session_store import save_cookies
from .history_fetcher import fetch_orders_per_year_with_scrapy


_worker_lock = threading.Lock()
_worker_thread = None


def _parse_proxy() -> dict | None:
	proxy = os.getenv("PROXY_SERVER") or os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")
	if not proxy:
		return None
	return {"server": proxy}


def _humanize_page(page):
	try:
		# Di chuyển chuột và scroll nhẹ để giống người dùng
		w = page.viewport_size["width"] if page.viewport_size else 1280
		h = page.viewport_size["height"] if page.viewport_size else 800
		for _ in range(3):
			x = random.randint(50, w - 50)
			y = random.randint(50, h - 50)
			page.mouse.move(x, y, steps=random.randint(8, 20))
			page.wait_for_timeout(random.randint(100, 300))
		page.mouse.wheel(0, random.randint(200, 600))
		page.wait_for_timeout(random.randint(100, 300))
	except Exception:
		pass


def _make_persistent_context(p, engine: str, headless: bool, slow_mo_ms: int, ua: str, viewport: dict):
	# Dùng profile riêng theo email sẽ được set ở nơi gọi bằng user_data_dir
	launch = p.firefox.launch_persistent_context if engine == "firefox" else p.chromium.launch_persistent_context
	proxy = _parse_proxy()
	ctx = launch(
		user_data_dir=os.getenv("PLAYWRIGHT_PROFILE_DIR", os.path.join(".playwright", "profiles")),
		headless=headless,
		slow_mo=slow_mo_ms,
		user_agent=ua,
		locale="en-US",
		timezone_id="America/Los_Angeles",
		viewport=viewport,
		extra_http_headers={
			"Accept-Language": "en-US,en;q=0.9",
			"DNT": "1",
			"Upgrade-Insecure-Requests": "1",
		},
		proxy=proxy,
		# Prefs cho Firefox để hạn chế chặn (không bật RFP)
		**({"firefox_user_prefs": {"privacy.resistFingerprinting": False, "dom.webdriver.enabled": False}} if engine == "firefox" else {}),
	)
	return ctx


def _make_browser_and_context(p, engine: str, headless: bool, slow_mo_ms: int):
	ua_firefox = (
		"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:141.0) Gecko/20100101 Firefox/141.0"
	)
	ua_chrome = (
		"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
	)
	ua = ua_firefox if engine == "firefox" else ua_chrome

	viewport = {
		"width": random.randint(1280, 1440),
		"height": random.randint(720, 950),
	}

	proxy = _parse_proxy()
	if os.getenv("PLAYWRIGHT_PERSIST", "0").lower() in ("1", "true", "yes"):
		context = _make_persistent_context(p, engine, headless, slow_mo_ms, ua, viewport)
		browser = context.browser
	else:
		browser = (p.firefox if engine == "firefox" else p.chromium).launch(
			headless=headless,
			slow_mo=slow_mo_ms,
			proxy=proxy,
		)
		context = browser.new_context(
			user_agent=ua,
			locale="en-US",
			timezone_id="America/Los_Angeles",
			viewport=viewport,
			extra_http_headers={
				"Accept-Language": "en-US,en;q=0.9",
				"DNT": "1",
				"Upgrade-Insecure-Requests": "1",
			},
		)

	# Script giảm tín hiệu bot (navigator properties phổ biến)
	context.add_init_script(
		"""
		Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
		Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3]});
		Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
		try { window.chrome = { runtime: {} }; } catch(e) {}
		"""
	)

	page = context.new_page()
	return browser, context, page


def _playwright_login_and_cookies(email: str, password: str) -> List[dict]:
	try:
		from playwright.sync_api import sync_playwright  # lazy import
	except ImportError:
		return []

	# Đọc cấu hình hiển thị GUI từ ENV
	headless_env = os.getenv("PLAYWRIGHT_HEADLESS")
	if headless_env is None:
		headless_default = os.getenv("FLASK_ENV", "").lower() != "development"
	else:
		headless_default = headless_env.lower() not in ("0", "false", "no")
	slow_mo_ms = int(os.getenv("PLAYWRIGHT_SLOWMO_MS", "0") or 0)
	keep_open = os.getenv("PLAYWRIGHT_KEEP_OPEN", "0").lower() in ("1", "true", "yes")

	with sync_playwright() as p:
		for engine in ("firefox", "chromium"):
			try:
				browser, context, page = _make_browser_and_context(p, engine, headless_default, slow_mo_ms)

				# 1) Trang chủ → click trực tiếp a.account-sign-in-link
				page.goto("https://www.rei.com/", wait_until="domcontentloaded")
				_humanize_page(page)
				try:
					link = page.locator("a.account-sign-in-link").first
					link.wait_for(state="visible", timeout=20000)
					link.scroll_into_view_if_needed()
					link.click()
				except Exception:
					# Fallback: dùng JS click để vượt overlay
					try:
						page.evaluate("document.querySelector('a.account-sign-in-link')?.click()")
					except Exception:
						pass

				# 2) Chờ tới /login rồi điền form
				try:
					page.wait_for_url(lambda url: "/login" in url or "/user/login" in url, timeout=25000)
				except Exception:
					page.goto("https://www.rei.com/login?toUrl=/", wait_until="domcontentloaded")

				# Access Denied guard
				body_text = (page.locator("body").inner_text(timeout=3000) or "") if page else ""
				if "Access Denied" in body_text:
					if keep_open:
						while browser.is_connected():
							time.sleep(0.5)
					else:
						browser.close()
					continue

				page.locator("#logonId").fill(email)
				page.locator("#password").fill(password)
				btn = page.locator("button[data-ui='button-submit']").first
				if btn.count() == 0:
					btn = page.locator("#Logon button[type=submit]").first
				btn.click()

				try:
					page.wait_for_load_state("networkidle", timeout=25000)
				except Exception:
					page.wait_for_timeout(2000)

				# Kiểm tra bị chặn sau submit
				body_text = (page.locator("body").inner_text(timeout=3000) or "")
				if "Access Denied" in body_text:
					if keep_open:
						while browser.is_connected():
							time.sleep(0.5)
					else:
						browser.close()
					continue

				cookies = context.cookies()
				if keep_open:
					while browser.is_connected():
						time.sleep(0.5)
				else:
					browser.close()
				return cookies
			except Exception:
				try:
					if keep_open:
						while browser.is_connected():
							time.sleep(0.5)
					else:
						browser.close()
				except Exception:
					pass
				continue
	return []


def _fetch_orders_per_year(email: str, password: str):
	cookies = _playwright_login_and_cookies(email, password)
	rei_cookies = [c for c in cookies if ".rei.com" in (c.get("domain") or "")]
	can_login = len(rei_cookies) > 0
	if not can_login:
		return False, {}, []

	# Lưu cookie jar ra file (tuỳ chọn) và trả về để caller lưu DB
	save_cookies(email, rei_cookies)

	# Tính năm từ 2014 đến hiện tại
	now = datetime.utcnow().year
	years = list(range(2014, now + 1))

	# Gọi Scrapy để lấy thống kê theo năm
	per_year = fetch_orders_per_year_with_scrapy(years, rei_cookies)
	return True, per_year, rei_cookies


def _process_accounts(app, emails: List[str]) -> None:
	with app.app_context():
		for email in emails:
			account = Account.query.filter_by(email=email).one_or_none()
			if account is None:
				continue
			can_login, per_year, cookies = _fetch_orders_per_year(account.email, account.password)

			total = 0
			for year, count in (per_year or {}).items():
				total += int(count)
				stat = AccountYearStat.query.filter_by(account_id=account.id, year=year).one_or_none()
				if stat is None:
					stat = AccountYearStat(account_id=account.id, year=year, orders_count=int(count))
					db.session.add(stat)
				else:
					stat.orders_count = int(count)

			account.can_login = bool(can_login)
			account.total_orders = int(total)
			account.last_checked_at = datetime.utcnow()
			if cookies:
				try:
					account.cookies_json = json.dumps(cookies, ensure_ascii=False)
				except Exception:
					pass
			db.session.commit()
			time.sleep(0.2)


def enqueue_accounts_check(emails: List[str]) -> None:
	global _worker_thread
	if not emails:
		return
	app = current_app._get_current_object()

	def target():
		try:
			_process_accounts(app, emails)
		finally:
			global _worker_thread
			with _worker_lock:
				_worker_thread = None

	with _worker_lock:
		if _worker_thread is None or not _worker_thread.is_alive():
			_wooder = threading.Thread(target=target, daemon=True)
			_wooder.start()
			_worker_thread = _wooder
