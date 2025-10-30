import os
import threading
from typing import List, Optional, Tuple
import requests
import time
import logging
from urllib.parse import urlsplit


_proxy_list: List[str] = []
_proxy_idx = 0
_lock = threading.RLock()
_logger = logging.getLogger("proxy")


def _load_proxies() -> None:
	global _proxy_list, _proxy_idx
	path = os.getenv("PROXY_LIST_PATH", os.path.join(os.getcwd(), "proxy.txt"))
	if not os.path.exists(path):
		_proxy_list = []
		_logger.warning("Proxy list file not found: %s", path)
		return
	scheme = os.getenv("PROXY_SCHEME", "socks5").lower()
	with open(path, "r", encoding="utf-8", errors="ignore") as f:
		lines = [ln.strip() for ln in f.readlines()]
		items: List[str] = []
		for idx, ln in enumerate(lines, start=1):
			if not ln or ln.startswith("#"):
				continue
			if "://" not in ln:
				# Hỗ trợ Host:Port:Username:Password -> scheme://username:password@host:port
				parts = ln.split(":")
				if len(parts) >= 4:
					host, port, user, pwd = parts[0], parts[1], parts[2], ":".join(parts[3:])
					ln = f"{scheme}://{user}:{pwd}@{host}:{port}"
				else:
					ln = f"{scheme}://" + ln
			items.append(ln)
			# Log chi tiết sau khi parse (mask password)
			split = urlsplit(ln)
			user = split.username or ""
			pwd = split.password or ""
			pwd_mask = ("*" * max(0, len(pwd) - 2)) + pwd[-2:] if pwd else ""
			_host = split.hostname or ""
			_port = split.port or ""
			_logger.info(
				"Proxy parsed | idx=%s | scheme=%s | host=%s | port=%s | user=%s | pwd=%s",
				idx,
				split.scheme,
				_host,
				_port,
				user,
				pwd_mask,
			)
		_proxy_list = items
		_proxy_idx = 0
		_logger.info("Loaded proxy list | count=%s | path=%s", len(_proxy_list), path)


def _update_if_needed():
	if not _proxy_list:
		_load_proxies()


def get_next_proxy() -> Optional[str]:
	global _proxy_idx
	with _lock:
		_update_if_needed()
		if not _proxy_list:
			return None
		proxy = _proxy_list[_proxy_idx % len(_proxy_list)]
		_proxy_idx = (_proxy_idx + 1) % len(_proxy_list)
		return proxy


def check_proxy_live(proxy_url: str, timeout_sec: Optional[float] = None) -> Tuple[bool, Optional[str]]:
	"""Kiểm tra proxy bằng api.ipify.org; trả về (is_live, ip)."""
	if timeout_sec is None:
		try:
			timeout_sec = float(os.getenv("PROXY_CHECK_TIMEOUT", "2"))
		except Exception:
			timeout_sec = 2.0
	start = time.monotonic()
	try:
		# Cho phép dùng scheme khác cho bước check (ví dụ http) so với scheme dùng lúc connect (ví dụ socks5)
		check_scheme = os.getenv("PROXY_CHECK_SCHEME", "http").lower()
		parsed = urlsplit(proxy_url)
		check_url = proxy_url
		if parsed.scheme and parsed.scheme != check_scheme:
			check_url = f"{check_scheme}://{parsed.username+':' if parsed.username else ''}{parsed.password+'@' if parsed.password else ''}{parsed.hostname}:{parsed.port}"

		_logger.info("Proxy check START | proxy=%s | check_url=%s | timeout=%.1fs", proxy_url, check_url, timeout_sec)
		s = requests.Session()
		s.proxies.update({"http": check_url, "https": check_url})
		r = s.get("https://api.ipify.org?format=json", timeout=timeout_sec)
		r.raise_for_status()
		ip = r.json().get("ip")
		dur = (time.monotonic() - start) * 1000
		_logger.info("Proxy check OK | proxy=%s | ip=%s | %.0fms", proxy_url, ip, dur)
		return True, ip
	except Exception as e:
		dur = (time.monotonic() - start) * 1000
		_logger.warning("Proxy check FAIL | proxy=%s | %.0fms | err=%s", proxy_url, dur, getattr(e, "__class__", type(e)).__name__)
		return False, None


def get_working_proxy(max_rounds: int = 1) -> Tuple[Optional[str], Optional[str]]:
	"""Chọn proxy hoạt động với số lần thử giới hạn (mặc định 3), không giữ lock khi gọi mạng."""
	enabled = os.getenv("PROXY_CHECK_ENABLED", "1").lower() not in ("0", "false", "no")
	if not enabled:
		p = get_next_proxy()
		_logger.info("Proxy check DISABLED | selected=%s", p)
		return p, None

	try:
		max_tries_env = int(os.getenv("PROXY_CHECK_MAX_TRIES", "3"))
	except Exception:
		max_tries_env = 3

	tries = 0
	while tries < max_tries_env:
		with _lock:
			_update_if_needed()
			if not _proxy_list:
				_logger.warning("Proxy list empty; no proxy available")
				return None, None
			proxy = _proxy_list[_proxy_idx % len(_proxy_list)]
			globals()["_proxy_idx"] = (_proxy_idx + 1) % len(_proxy_list)
		ok, ip = check_proxy_live(proxy)
		if ok:
			return proxy, ip
		tries += 1
	_logger.warning("No live proxy after %s tries", tries)
	return None, None
