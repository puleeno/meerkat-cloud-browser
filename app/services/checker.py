import threading
import time
from datetime import datetime
from typing import Dict, List
import os

from flask import current_app

from ..extensions import db
from ..models import Account, AccountYearStat
from .session_store import save_cookies
from .history_fetcher import fetch_orders_per_year_with_scrapy


_worker_lock = threading.Lock()
_worker_thread = None


def _playwright_login_and_cookies(email: str, password: str) -> List[dict]:
	try:
		from playwright.sync_api import sync_playwright  # lazy import để tránh ImportError khi migrate/chưa cài
	except ImportError:
		# Chưa cài playwright
		return []

	with sync_playwright() as p:
		# Đọc cấu hình hiển thị GUI từ ENV
		headless_env = os.getenv("PLAYWRIGHT_HEADLESS")
		if headless_env is None:
			# Mặc định: development -> GUI (headless False), còn lại headless True
			headless = os.getenv("FLASK_ENV", "").lower() != "development"
		else:
			headless = headless_env.lower() not in ("0", "false", "no")
		slow_mo_ms = int(os.getenv("PLAYWRIGHT_SLOWMO_MS", "0") or 0)

		browser = p.firefox.launch(headless=headless, slow_mo=slow_mo_ms)
		context = browser.new_context()
		page = context.new_page()

		login_url = os.getenv("REI_LOGIN_URL", "https://www.rei.com/")
		page.goto(login_url, wait_until="domcontentloaded")

		# Heuristic: tìm các input email/password thường gặp
		selectors = [
			("input[name=email]", email),
			("input[type=email]", email),
			("input#email", email),
			("input[name=username]", email),
			("input[type=password]", password),
			("input#password", password),
		]

		for sel, val in selectors:
			try:
				el = page.query_selector(sel)
				if el:
					el.fill(val)
			except Exception:
				pass

		# Thử submit
		for btn_sel in ["button[type=submit]", "button[name=submit]", "button#sign-in", "button:has-text('Sign in')"]:
			try:
				btn = page.query_selector(btn_sel)
				if btn:
					btn.click()
					break
			except Exception:
				pass

		page.wait_for_timeout(3000)
		cookies = context.cookies()
		browser.close()
		return cookies


def _fetch_orders_per_year(email: str, password: str):
	cookies = _playwright_login_and_cookies(email, password)
	rei_cookies = [c for c in cookies if ".rei.com" in (c.get("domain") or "")]
	can_login = len(rei_cookies) > 0
	if not can_login:
		return False, {}

	# Lưu cookie jar
	save_cookies(email, rei_cookies)

	# Tính năm từ 2014 đến hiện tại
	now = datetime.utcnow().year
	years = list(range(2014, now + 1))

	# Gọi Scrapy để lấy thống kê theo năm
	per_year = fetch_orders_per_year_with_scrapy(years, rei_cookies)
	return True, per_year


def _process_accounts(emails: List[str]) -> None:
	with current_app.app_context():
		for email in emails:
			account = Account.query.filter_by(email=email).one_or_none()
			if account is None:
				continue
			can_login, per_year = _fetch_orders_per_year(account.email, account.password)

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
			db.session.commit()
			time.sleep(0.2)


def enqueue_accounts_check(emails: List[str]) -> None:
	global _worker_thread
	if not emails:
		return

	def target():
		try:
			_process_accounts(emails)
		finally:
			global _worker_thread
			with _worker_lock:
				_worker_thread = None

	with _worker_lock:
		if _worker_thread is None or not _worker_thread.is_alive():
			_wooder = threading.Thread(target=target, daemon=True)
			_wooder.start()
			_worker_thread = _wooder
