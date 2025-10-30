import threading
import time
from datetime import datetime
from typing import Dict, List
import os
import random
import json
import shutil
import sys
import asyncio

# Windows: cần ProactorEventLoop cho subprocess (Playwright) khi chạy trong thread
if sys.platform.startswith("win"):
	try:
		asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
	except Exception:
		pass

from flask import current_app

from ..extensions import db
from ..models import Account, AccountYearStat
from .session_store import save_cookies
from .history_fetcher import fetch_orders_per_year_with_scrapy
from .telegram_bot import send_message, send_photo, send_photo_bytes


_worker_lock = threading.Lock()
_worker_thread = None


def _safe_key(email: str) -> str:
	return email.lower().replace("@", "_at_").replace("/", "_").replace("\\", "_")


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
			page.wait_for_timeout(random.randint(120, 260))
		page.mouse.wheel(0, random.randint(200, 600))
		page.wait_for_timeout(random.randint(120, 260))
	except Exception:
		pass


def _maybe_random_browse(page):
	"""Trước khi login, lướt nhẹ và có thể click ngẫu nhiên 1 item/link."""
	try:
		# Scroll vài lần
		for _ in range(random.randint(1, 3)):
			page.mouse.wheel(0, random.randint(300, 900))
			page.wait_for_timeout(random.randint(200, 500))
		# 50% cơ hội click ngẫu nhiên 1 link có href hợp lệ
		if random.random() < 0.5:
			candidates = page.locator("a[href]:visible").all()[:200]
			if candidates:
				el = random.choice(candidates)
				href = el.get_attribute("href") or ""
				if href and not href.startswith("#") and "login" not in href and "signin" not in href:
					try:
						el.scroll_into_view_if_needed()
						el.click(timeout=2000)
						page.wait_for_timeout(random.randint(400, 900))
						# quay lại trang chủ
						page.go_back(timeout=5000)
					except Exception:
						pass
	except Exception:
		pass


def _slow_type(locator, value: str):
	"""Gõ ký tự có độ trễ để giống người dùng (đã rút ngắn)."""
	try:
		locator.click()
		locator.fill("")
		for ch in value:
			locator.type(ch, delay=random.randint(40, 90))
			# nghỉ ngắn thỉnh thoảng
			if random.random() < 0.1:
				locator.page.wait_for_timeout(random.randint(60, 120))
	except Exception:
		# fallback fill nếu type thất bại
		try:
			locator.fill(value)
		except Exception:
			pass


def _make_persistent_context(p, engine: str, headless: bool, slow_mo_ms: int, ua: str, viewport: dict, email: str):
	launch = p.firefox.launch_persistent_context if engine == "firefox" else p.chromium.launch_persistent_context
	proxy = _parse_proxy()
	base_dir = os.getenv("PLAYWRIGHT_PROFILE_DIR", os.path.join(".playwright", "profiles"))
	os.makedirs(base_dir, exist_ok=True)
	user_dir = os.path.join(base_dir, _safe_key(email))
	ctx = launch(
		user_data_dir=user_dir,
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
		**({"firefox_user_prefs": {"privacy.resistFingerprinting": False, "dom.webdriver.enabled": False}} if engine == "firefox" else {}),
	)
	return ctx, user_dir


def _make_browser_and_context(p, engine: str, headless: bool, slow_mo_ms: int, email: str):
	ua_firefox = (
		"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:141.0) Gecko/20100101 Firefox/141.0"
	)
	ua_chrome = (
		"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
	)
	ua = ua_firefox if engine == "firefox" else ua_chrome

	viewport = {"width": random.randint(1280, 1440), "height": random.randint(720, 950)}

	profile_dir = None
	proxy = _parse_proxy()
	if os.getenv("PLAYWRIGHT_PERSIST", "0").lower() in ("1", "true", "yes"):
		context, profile_dir = _make_persistent_context(p, engine, headless, slow_mo_ms, ua, viewport, email)
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

	context.add_init_script(
		"""
		Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
		Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3]});
		Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
		try { window.chrome = { runtime: {} }; } catch(e) {}
		"""
	)

	page = context.new_page()
	return browser, context, page, profile_dir


def _playwright_login_and_cookies(email: str, password: str) -> tuple[list[dict], Dict[str, str]]:
	try:
		from playwright.sync_api import sync_playwright
	except ImportError:
		return [], {}

	headless_env = os.getenv("PLAYWRIGHT_HEADLESS")
	if headless_env is None:
		headless_default = os.getenv("FLASK_ENV", "").lower() != "development"
	else:
		headless_default = headless_env.lower() not in ("0", "false", "no")
	slow_mo_ms = int(os.getenv("PLAYWRIGHT_SLOWMO_MS", "0") or 0)
	keep_open = os.getenv("PLAYWRIGHT_KEEP_OPEN", "0").lower() in ("1", "true", "yes")
	delete_profile = os.getenv("PLAYWRIGHT_DELETE_PROFILE", "1").lower() in ("1", "true", "yes")
	persist_enabled = os.getenv("PLAYWRIGHT_PERSIST", "0").lower() in ("1", "true", "yes")

	with sync_playwright() as p:
		for engine in ("firefox", "chromium"):
			browser = None
			profile_dir = None
			try:
				# build UA to also return as header later
				ua_firefox = (
					"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:141.0) Gecko/20100101 Firefox/141.0"
				)
				ua_chrome = (
					"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
				)
				ua_used = ua_firefox if engine == "firefox" else ua_chrome

				browser, context, page, profile_dir = _make_browser_and_context(
					p, engine, headless_default, slow_mo_ms, email
				)

				# capture outgoing request headers for rei.com
				headers_seen: Dict[str, str] = {}
				def _on_req(req):
					try:
						if "rei.com" in req.url:
							for k, v in (req.headers or {}).items():
								headers_seen[k.lower()] = v
					except Exception:
						pass
				page.on("request", _on_req)

				page.goto("https://www.rei.com/", wait_until="domcontentloaded")
				send_message(f"Bắt đầu kiểm tra tài khoản: {email}")
				_humanize_page(page)
				_maybe_random_browse(page)
				try:
					link = page.locator("a.account-sign-in-link").first
					link.wait_for(state="visible", timeout=20000)
					link.scroll_into_view_if_needed()
					link.click()
				except Exception:
					try:
						page.evaluate("document.querySelector('a.account-sign-in-link')?.click()")
					except Exception:
						pass

				try:
					page.wait_for_url(lambda url: "/login" in url or "/user/login" in url, timeout=25000)
				except Exception:
					page.goto("https://www.rei.com/login?toUrl=/", wait_until="domcontentloaded")

				body_text = (page.locator("body").inner_text(timeout=3000) or "") if page else ""
				if "Access Denied" in body_text:
					if keep_open:
						while browser.is_connected():
							time.sleep(0.5)
					else:
						browser.close()
					if persist_enabled and delete_profile and profile_dir and not keep_open:
						shutil.rmtree(profile_dir, ignore_errors=True)
					continue

				# type slowly
				_slow_type(page.locator("#logonId"), email)
				_slow_type(page.locator("#password"), password)
				btn = page.locator("button[data-ui='button-submit']").first
				if btn.count() == 0:
					btn = page.locator("#Logon button[type=submit]").first
				# chụp ảnh trước khi submit
				try:
					img_bytes = page.screenshot(full_page=False)
					send_photo_bytes(img_bytes, caption=f"Trước khi submit: {email}", filename=f"{_safe_key(email)}-before-submit.png")
				except Exception:
					# Fallback: lưu file nếu cần
					screens_dir = os.path.join("instance", "screens")
					os.makedirs(screens_dir, exist_ok=True)
					before_path = os.path.join(screens_dir, f"{_safe_key(email)}-before-submit-{int(time.time())}.png")
					try:
						page.screenshot(path=before_path, full_page=False)
						send_photo(before_path, caption=f"Trước khi submit: {email}")
					except Exception:
						pass
				btn.click()

				try:
					page.wait_for_load_state("networkidle", timeout=25000)
				except Exception:
					page.wait_for_timeout(2000)

				body_text = (page.locator("body").inner_text(timeout=3000) or "")
				if "Access Denied" in body_text:
					if keep_open:
						while browser.is_connected():
							time.sleep(0.5)
					else:
						browser.close()
					if persist_enabled and delete_profile and profile_dir and not keep_open:
						shutil.rmtree(profile_dir, ignore_errors=True)
					continue

				cookies = context.cookies()

				# chụp ảnh sau khi login
				try:
					img2 = page.screenshot(full_page=False)
					send_photo_bytes(img2, caption=f"Sau khi login: {email}", filename=f"{_safe_key(email)}-after-login.png")
				except Exception:
					try:
						screens_dir = os.path.join("instance", "screens")
						os.makedirs(screens_dir, exist_ok=True)
						after_path = os.path.join(screens_dir, f"{_safe_key(email)}-after-login-{int(time.time())}.png")
						page.screenshot(path=after_path, full_page=False)
						send_photo(after_path, caption=f"Sau khi login: {email}")
					except Exception:
						pass

				# build final headers from seen + our known values
				final_headers: Dict[str, str] = {
					"User-Agent": ua_used,
					"Accept": headers_seen.get("accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"),
					"Accept-Language": headers_seen.get("accept-language", "en-US,en;q=0.9"),
					"Accept-Encoding": headers_seen.get("accept-encoding", "gzip, deflate, br, zstd"),
					"Connection": headers_seen.get("connection", "keep-alive"),
					"Upgrade-Insecure-Requests": headers_seen.get("upgrade-insecure-requests", "1"),
				}
				# include sec-* if present
				for k in list(headers_seen.keys()):
					if k.startswith("sec-"):
						final_headers[k.title()] = headers_seen[k]

				if keep_open:
					while browser.is_connected():
						time.sleep(0.5)
				else:
					browser.close()
				if persist_enabled and delete_profile and profile_dir and not keep_open:
					shutil.rmtree(profile_dir, ignore_errors=True)
				return cookies, final_headers
			except Exception:
				try:
					if keep_open and browser is not None:
						while browser.is_connected():
							time.sleep(0.5)
					elif browser is not None:
						browser.close()
				except Exception:
					pass
				if persist_enabled and delete_profile and profile_dir and not keep_open:
					shutil.rmtree(profile_dir, ignore_errors=True)
				continue
	return [], {}


def _fetch_orders_per_year(email: str, password: str):
	cookies, headers = _playwright_login_and_cookies(email, password)
	rei_cookies = [c for c in cookies if ".rei.com" in (c.get("domain") or "")]
	can_login = len(rei_cookies) > 0
	if not can_login:
		return False, {}, [], {}

	save_cookies(email, rei_cookies)

	now = datetime.utcnow().year
	years = list(range(2014, now + 1))

	per_year_counts, raw_map = fetch_orders_per_year_with_scrapy(years, rei_cookies, headers=headers)
	return True, per_year_counts, rei_cookies, headers, raw_map


def _process_accounts(app, emails: List[str]) -> None:
	with app.app_context():
		for email in emails:
			account = Account.query.filter_by(email=email).one_or_none()
			if account is None:
				continue
			can_login, per_year, cookies, headers, raw_map = _fetch_orders_per_year(account.email, account.password)

			total = 0
			for year, count in (per_year or {}).items():
				total += int(count)
				stat = AccountYearStat.query.filter_by(account_id=account.id, year=year).one_or_none()
				if stat is None:
					stat = AccountYearStat(account_id=account.id, year=year, orders_count=int(count))
					db.session.add(stat)
				else:
					stat.orders_count = int(count)
				if raw_map:
					stat.raw_json = json.dumps(raw_map[year], ensure_ascii=False)

			# Gửi log Telegram theo từng năm
			try:
				if per_year:
					years_text = "\n".join([f"- {y}: {per_year[y]} đơn" for y in sorted(per_year.keys())])
					send_message(f"Kết quả đơn hàng cho {email}:\n{years_text}\nTổng: {total}")
			except Exception:
				pass

			account.can_login = bool(can_login)
			account.total_orders = int(total)
			account.last_checked_at = datetime.utcnow()
			if cookies:
				try:
					account.cookies_json = json.dumps(cookies, ensure_ascii=False)
				except Exception:
					pass
			if headers:
				try:
					account.headers_json = json.dumps(headers, ensure_ascii=False)
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


def run_accounts_check_sync(emails: List[str]) -> None:
	"""Chạy kiểm tra đồng bộ (blocking) cho danh sách emails."""
	app = current_app._get_current_object()
	_process_accounts(app, emails)
