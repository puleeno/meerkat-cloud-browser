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
import logging
from urllib.parse import urlsplit

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
from .proxy_pool import get_working_proxy


_worker_lock = threading.Lock()
_worker_thread = None

logger = logging.getLogger("batch")


def _safe_key(email: str) -> str:
	return email.lower().replace("@", "_at_").replace("/", "_").replace("\\", "_")


def _pick_proxy_url() -> tuple[str | None, str | None]:
	proxy, ip = get_working_proxy(max_rounds=1)
	if proxy:
		return proxy, ip
	# fallback env
	env_proxy = os.getenv("PROXY_SERVER") or os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")
	return (env_proxy or None), None


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
	"""Gõ ký tự có độ trễ để giống người dùng (nhanh hơn)."""
	try:
		locator.click()
		locator.fill("")
		for ch in value:
			locator.type(ch, delay=random.randint(5, 50))
			# nghỉ rất ngắn ngẫu nhiên
			if random.random() < 0.08:
				locator.page.wait_for_timeout(random.randint(15, 60))
	except Exception:
		# fallback fill nếu type thất bại
		try:
			locator.fill(value)
		except Exception:
			pass


def _wait_login_page(page):
	"""Chờ trang login ổn định: form #Logon và 2 field có mặt."""
	page.wait_for_selector("#Logon", state="visible", timeout=20000)
	page.wait_for_selector("#logonId", state="visible", timeout=10000)
	page.wait_for_selector("#password", state="visible", timeout=10000)
	# đợi network idle ngắn để hạn chế reload trong lúc gõ
	try:
		page.wait_for_load_state("networkidle", timeout=3000)
	except Exception:
		pass


def _extract_login_error(page) -> str | None:
    # Đợi ngắn để UI render thông báo
    try:
        page.wait_for_timeout(400)
    except Exception:
        pass
    # Thử nhiều vị trí thông báo lỗi phổ biến trên REI và chung
    # Ưu tiên các selector đặc thù REI
    selectors = [
        "[data-ui='error-credentials'] .alert-text",
        "p.alert.alert-danger .alert-text",
        "#page-content [data-ui='error-credentials'] .alert-text",
        ".error-msg [data-ui='login-module-error-invalid-fields'] .msg",
        "[role='alert']",
        "div[aria-live='assertive']",
        "div[aria-live='polite']",
        ".alert, .alert-danger, .c-alert__message",
        ".error, .field-error, .form-error, .inline-error",
        "#loginError, #error, #auth-error",
        "span.sr-only, .sr-only",
        "[data-test='error'], [data-testid='error'], [data-qa='error']",
        "[class*='error']",
    ]
    for sel in selectors:
        try:
            els = page.query_selector_all(sel) or []
            for el in els:
                try:
                    vis = False
                    try:
                        vis = el.is_visible()
                    except Exception:
                        pass
                    txt = (el.inner_text() or el.text_content() or "").strip()
                    if txt and (vis or len(txt) > 5):
                        return txt
                except Exception:
                    continue
        except Exception:
            continue
    # Fallback: thử đọc lỗi từ JSON nhúng trong page (REI để trong data-client-store="page-meta-data")
    try:
        el = page.locator("script[data-client-store='page-meta-data']").first
        if el and el.count() > 0:
            raw = (el.inner_text() or el.text_content() or "").strip()
            if raw:
                try:
                    data = json.loads(raw)
                    err = (data.get("errorCodes") or "").strip()
                    if err:
                        return err
                except Exception:
                    pass
    except Exception:
        pass
    return None


def _classify_login_failure(page, error_text: str) -> str:
    """Trả về: 'credentials' | 'blocked' | 'proxy' | 'unknown'"""
    txt = (error_text or "").lower()
    try:
        body_text = (page.inner_text("body") or "").lower()
    except Exception:
        body_text = ""
    url_now = ""
    try:
        url_now = page.url or ""
    except Exception:
        pass

    cred_markers = [
        "doesn't match our records",
        "doesnt match our records",
        "information you entered",
        "incorrect",
        "invalid",
        "mismatch",
        "wrong password",
        "account not found",
    ]
    blocked_markers = [
        "access denied",
        "forbidden",
        "403",
        "captcha",
        "verify you are human",
        "bot detected",
        "temporarily blocked",
    ]

    if any(k in txt for k in cred_markers):
        return "credentials"
    if any(k in body_text for k in cred_markers):
        return "credentials"

    if any(k in body_text for k in blocked_markers) or any(k in (url_now or "").lower() for k in ["access", "forbidden", "captcha", "blocked", "403"]):
        return "blocked"

    # Nếu không trích xuất được thông điệp cụ thể, thường là lỗi kết nối/proxy
    if (error_text or "").strip().lower() == "login failed":
        return "proxy"

    return "unknown"


def _build_tg_message_url(message_id: int | str | None) -> str | None:
    if not message_id:
        return None
    from os import getenv
    mid = str(message_id)
    username = getenv("TELEGRAM_CHAT_USERNAME")
    chat_id = getenv("TELEGRAM_CHAT_ID")
    # Cho phép override base URL nếu dùng bên thứ ba (ví dụ tgstat, private viewer)
    custom_base = getenv("TELEGRAM_CHAT_URL_BASE")
    if custom_base:
        try:
            return f"{custom_base.rstrip('/')}/{mid}"
        except Exception:
            pass
    if username:
        return f"https://t.me/{username}/{mid}"
    if chat_id and str(chat_id).startswith("-100"):
        return f"https://t.me/c/{str(chat_id)[4:]}/{mid}"
    # Không đủ thông tin để build URL hợp lệ
    return None


def _fill_with_retries(page, selector: str, value: str, use_typing: bool = True, retries: int = 3):
	last_err = None
	for _ in range(max(1, retries)):
		try:
			_wait_login_page(page)
			loc = page.locator(selector)
			if use_typing:
				_slow_type(loc, value)
			else:
				loc.fill(value)
			# xác nhận giá trị đã được điền (nếu có thể)
			try:
				current = page.locator(selector).input_value(timeout=1000)
				if current:
					return True
			except Exception:
				return True
		except Exception as e:
			last_err = e
			# có thể trang vừa reload → thử lại
			continue
	if last_err:
		raise last_err
	return False


def _make_persistent_context(p, engine: str, headless: bool, slow_mo_ms: int, ua: str, viewport: dict, email: str, playwright_proxy: dict | None):
	launch = p.firefox.launch_persistent_context if engine == "firefox" else p.chromium.launch_persistent_context
	proxy = playwright_proxy
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


def _make_browser_and_context(p, engine: str, headless: bool, slow_mo_ms: int, email: str, playwright_proxy: dict | None):
	ua_firefox = (
		"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:141.0) Gecko/20100101 Firefox/141.0"
	)
	ua_chrome = (
		"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
	)
	ua = ua_firefox if engine == "firefox" else ua_chrome

	viewport = {"width": random.randint(1280, 1440), "height": random.randint(720, 950)}

	profile_dir = None
	proxy = playwright_proxy
	if os.getenv("PLAYWRIGHT_PERSIST", "0").lower() in ("1", "true", "yes"):
		context, profile_dir = _make_persistent_context(p, engine, headless, slow_mo_ms, ua, viewport, email, proxy)
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


def _playwright_login_and_cookies(email: str, password: str) -> tuple[bool, list[dict], Dict[str, str], str | None]:
	try:
		from playwright.sync_api import sync_playwright
	except ImportError:
		return False, [], {}, None

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
		last_error_msg: str | None = None
		# Chọn proxy 1 lần/ tài khoản, áp dụng cho cả các thử nghiệm (firefox -> chromium)
		proxy_url, observed_ip = _pick_proxy_url()
		# Xây dựng proxy cho Playwright: server chỉ host:port, tách username/password
		playwright_proxy: dict | None = None
		if proxy_url:
			parsed = urlsplit(proxy_url)
			host = parsed.hostname
			port = parsed.port
			if host and port:
				scheme_override = os.getenv("PROXY_PLAYWRIGHT_SCHEME")
				scheme = (scheme_override or parsed.scheme or "http").lower()
				playwright_proxy = {
					"server": f"{scheme}://{host}:{port}",
				}
				if parsed.username:
					playwright_proxy["username"] = parsed.username
				if parsed.password:
					playwright_proxy["password"] = parsed.password
		try:
			if proxy_url:
				if observed_ip:
					send_message(f"[Proxy OK] {email} -> {proxy_url} | IP {observed_ip}")
				else:
					send_message(f"[Proxy Fallback] {email} -> {proxy_url}")
			else:
				send_message(f"[Proxy NONE] {email} -> không dùng proxy")
		except Exception:
			pass
		logger.info("Proxy | email=%s | proxy=%s | ip=%s", email, proxy_url, observed_ip)
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
					p, engine, headless_default, slow_mo_ms, email, playwright_proxy
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
				_humanize_page(page)                      # Cái này giả lập Scroll màn hình
				_maybe_random_browse(page)              # Tắt chỗ này nếu muốn loại bỏ giả lập lướt 1 page trước khi vào login
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
				_wait_login_page(page)

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

				# nhập với retry để xử lý case trang reload giữa chừng
				_fill_with_retries(page, "#logonId", email, use_typing=True, retries=4)
				_fill_with_retries(page, "#password", password, use_typing=True, retries=4)
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
				# sau submit, nếu bị redirect/refresh ngắn, chờ form biến mất
				try:
					page.wait_for_selector("#Logon", state="detached", timeout=5000)
				except Exception:
					pass

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
				after_login_msg_id = None
				try:
					img2 = page.screenshot(full_page=False)
					after_login_msg_id = send_photo_bytes(img2, caption=f"Sau khi login: {email}", filename=f"{_safe_key(email)}-after-login.png")
				except Exception:
					try:
						screens_dir = os.path.join("instance", "screens")
						os.makedirs(screens_dir, exist_ok=True)
						after_path = os.path.join(screens_dir, f"{_safe_key(email)}-after-login-{int(time.time())}.png")
						page.screenshot(path=after_path, full_page=False)
						msg_id_tmp = send_photo(after_path, caption=f"Sau khi login: {email}")
						url_tmp = _build_tg_message_url(msg_id_tmp)
						if url_tmp:
							_acc = locals().get('account')
							if _acc:
								_acc.after_login_telegram_message_url = url_tmp
								try:
									db.session.commit()
								except Exception:
									logger.exception("DB commit failed after saving after-login image URL (file) | email=%s", email)
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

				# Xác định login thành công dựa trên DOM 'Hi, '
				login_ok = False
				try:
					hi_text = page.locator('.account-nav-button__span-container').inner_text(timeout=4000) or ''
					if 'Hi' in hi_text:
						login_ok = True
				except Exception:
					login_ok = False

				# Trước khi đóng trình duyệt, nếu đăng nhập thất bại thì trích xuất lỗi khi DOM còn tồn tại
				err_text_before_close = None
				if not login_ok:
					try:
						err_text_before_close = _extract_login_error(page)
					except Exception:
						err_text_before_close = None

				if keep_open:
					while browser.is_connected():
						time.sleep(0.5)
				else:
					browser.close()
				if persist_enabled and delete_profile and profile_dir and not keep_open:
					shutil.rmtree(profile_dir, ignore_errors=True)
				if not login_ok:
					return False, [], {}, err_text_before_close
				return True, cookies, final_headers, None
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
				# cố gắng lấy thông điệp lỗi từ page nếu có
				try:
					if 'page' in locals() and page:
						last_error_msg = _extract_login_error(page)
				except Exception:
					last_error_msg = None
				continue
	return False, [], {}, last_error_msg


def _fetch_orders_per_year(email: str, password: str):
	login_ok, cookies, headers, error_message = _playwright_login_and_cookies(email, password)
	rei_cookies = [c for c in cookies if ".rei.com" in (c.get("domain") or "")]
	can_login = bool(login_ok and len(rei_cookies) > 0)
	if not can_login:
		return False, {}, [], {}, {}, (error_message or "Login failed")

	save_cookies(email, rei_cookies)

	now = datetime.utcnow().year
	years = list(range(2014, now + 1))

	# Dùng cùng proxy cho bước fetch như khi login để đồng nhất phiên/địa chỉ IP
	per_year_counts, raw_map = fetch_orders_per_year_with_scrapy(years, rei_cookies, headers=headers, proxy_url=None)
	return True, per_year_counts, rei_cookies, headers, raw_map, None


def _process_accounts(app, emails: List[str], on_event=None) -> None:
	with app.app_context():
		for email in emails:
			if on_event:
				try:
					on_event({"type": "start", "email": email})
				except Exception:
					pass
			logger.info("Process account start | email=%s", email)
			account = Account.query.filter_by(email=email).one_or_none()
			if account is None:
				logger.warning("Account not found | email=%s", email)
				continue
			can_login, per_year, cookies, headers, raw_map, login_error = _fetch_orders_per_year(account.email, account.password)

			# Nếu không đăng nhập được: đánh dấu thất bại và ghi thời điểm kiểm tra
			if not can_login:
				account.can_login = False
				account.last_checked_at = datetime.utcnow()
				account.error_message = login_error
				# Phân loại lỗi theo thông báo đã có (page không sẵn có ở đây)
				try:
					account.login_failure_type = _classify_login_failure(None, login_error or "")
				except Exception:
					account.login_failure_type = None
				# Gửi thông báo Telegram ngắn gọn về lỗi
				try:
					fail_text = login_error or "Login failed"
					fail_type = account.login_failure_type or "unknown"
					fail_msg_id = send_message(f"[Login FAIL] {email}\nType: {fail_type}\n{fail_text}")
					logger.info("TG notify fail | email=%s | msg_id=%s", email, str(fail_msg_id))
					if fail_msg_id:
						url_fail = _build_tg_message_url(fail_msg_id)
						logger.info("TG url built | email=%s | url=%s", email, url_fail)
						if url_fail:
							account.stats_status_telegram_message_url = url_fail
							db.session.commit()
				except Exception:
					logger.exception("TG notify exception | email=%s", email)
				logger.info("Login FAIL | email=%s", email)
				db.session.commit()
				if on_event:
					try:
						on_event({"type": "result", "email": email, "can_login": False})
					except Exception:
						pass
				time.sleep(0.1)
				continue

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

			stats_msg_id = None
			try:
				if per_year and can_login:
					years_text = "\n".join([f"- {y}: {per_year[y]} đơn" for y in sorted(per_year.keys())])
					stats_msg_id = send_message(f"Kết quả đơn hàng cho {email}:\n{years_text}\nTổng: {total}")
					logger.info("Orders | email=%s | total=%s | years=%s", email, total, sorted(per_year.keys()))
			except Exception:
				pass

			account.can_login = True
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
			# lưu message ids nếu có
			try:
				# Một số nhánh đặt tên biến id khác nhau, gom lại an toàn
				_tmp_id = locals().get('after_login_msg_id') or locals().get('msg_id_tmp')
				if _tmp_id:
					url = _build_tg_message_url(_tmp_id)
					if url:
						account.after_login_telegram_message_url = url
				if stats_msg_id:
					url2 = _build_tg_message_url(stats_msg_id)
					if url2:
						account.stats_status_telegram_message_url = url2
			except Exception:
				pass
			db.session.commit()
			try:
				ok_msg_id = send_message(f"[Login OK] {email} | Tổng đơn: {total}")
				if ok_msg_id and not stats_msg_id:
					url_ok = _build_tg_message_url(ok_msg_id)
					if url_ok:
						account.stats_status_telegram_message_url = url_ok
					db.session.commit()
			except Exception:
				pass
			logger.info("Login OK | email=%s | total=%s", email, total)
			if on_event:
				try:
					on_event({
						"type": "result",
						"email": email,
						"can_login": True,
						"total": total,
					})
				except Exception:
					pass
			time.sleep(0.2)


def enqueue_accounts_check(emails: List[str]) -> None:
	global _worker_thread
	if not emails:
		return
	app = current_app._get_current_object()

	def target():
		try:
			try:
				send_message(f"[Batch START] {len(emails)} tài khoản")
			except Exception:
				pass
			logger.info("Batch START | accounts=%s", len(emails))
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
	try:
		send_message(f"[Batch START] {len(emails)} tài khoản (sync)")
	except Exception:
		pass
	logger.info("Batch START (sync) | accounts=%s", len(emails))
	def _printer(evt):
		t = evt.get("type")
		if t == "start":
			print(f"[START] {evt.get('email')}")
		elif t == "result":
			if evt.get("can_login"):
				print(f"[OK]    {evt.get('email')} | total={evt.get('total')}")
			else:
				print(f"[FAIL]  {evt.get('email')}")
	_process_accounts(app, emails, on_event=_printer)
