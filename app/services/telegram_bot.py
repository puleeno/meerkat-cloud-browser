import os
import time
import requests
import logging
from typing import Optional


logger = logging.getLogger("telegram")
# Bảo đảm logger này in được cấp INFO vào handler gốc
try:
	logger.setLevel(logging.INFO)
	logger.propagate = True
except Exception:
	pass


def _enabled() -> bool:
	token = os.getenv("TELEGRAM_BOT_TOKEN")
	chat_id = os.getenv("TELEGRAM_CHAT_ID")
	enabled_flag = os.getenv("TELEGRAM_ENABLED", "1") not in ("0", "false", "no")
	enabled = bool(token and chat_id and enabled_flag)
	if not enabled:
		try:
			logger.info(
				"Telegram disabled | has_token=%s | has_chat_id=%s | enabled_flag=%s",
				bool(token), bool(chat_id), enabled_flag,
			)
		except Exception:
			pass
	else:
		try:
			logger.info("Telegram enabled | chat_id=%s", chat_id)
		except Exception:
			pass
	return enabled


def _base_url() -> str:
	return f"https://api.telegram.org/bot{os.getenv('TELEGRAM_BOT_TOKEN')}"


def send_message(text: str) -> Optional[int]:
	if not _enabled():
		return None
	try:
		r = requests.post(
			f"{_base_url()}/sendMessage",
			data={"chat_id": os.getenv("TELEGRAM_CHAT_ID"), "text": text},
			timeout=15,
		)
		if not r.ok:
			try:
				logger.warning("Telegram sendMessage failed | status=%s | body=%s", r.status_code, r.text[:300])
			except Exception:
				pass
			return None
		j = r.json()
		mid = (j.get("result") or {}).get("message_id")
		if mid is None:
			try:
				logger.warning("Telegram sendMessage no message_id | json=%s", str(j)[:300])
			except Exception:
				pass
		else:
			try:
				logger.info("Telegram sendMessage OK | chat_id=%s | message_id=%s", os.getenv("TELEGRAM_CHAT_ID"), str(mid))
			except Exception:
				pass
		return mid
	except Exception as e:
		try:
			logger.exception("Telegram sendMessage exception: %s", str(e)[:200])
		except Exception:
			pass
		return None


def send_photo(photo_path: str, caption: Optional[str] = None) -> Optional[int]:
	if not _enabled():
		# Nếu không bật, vẫn cố gắng dọn dẹp file
		try:
			if os.path.exists(photo_path):
				os.remove(photo_path)
		except Exception:
			pass
	return None
	try:
		with open(photo_path, "rb") as f:
			r = requests.post(
				f"{_base_url()}/sendPhoto",
				data={"chat_id": os.getenv("TELEGRAM_CHAT_ID"), "caption": caption or ""},
				files={"photo": f},
				timeout=30,
			)
			if not r.ok:
				try:
					logger.warning("Telegram sendPhoto failed | status=%s | body=%s", r.status_code, r.text[:300])
				except Exception:
					pass
				return None
			j = r.json()
			mid = (j.get("result") or {}).get("message_id")
			if mid is None:
				try:
					logger.warning("Telegram sendPhoto no message_id | json=%s", str(j)[:300])
				except Exception:
					pass
			else:
				try:
					logger.info("Telegram sendPhoto OK | chat_id=%s | message_id=%s", os.getenv("TELEGRAM_CHAT_ID"), str(mid))
				except Exception:
					pass
			return mid
	finally:
		# Luôn cố gắng xoá file sau khi gửi hoặc khi có lỗi
		try:
			if os.path.exists(photo_path):
				os.remove(photo_path)
		except Exception:
			pass


def send_photo_bytes(content: bytes, caption: Optional[str] = None, filename: str = "screenshot.png") -> Optional[int]:
	"""Gửi ảnh trực tiếp từ bytes, tránh lưu/xóa file tạm."""
	if not _enabled():
		return None
	try:
		r = requests.post(
			f"{_base_url()}/sendPhoto",
			data={"chat_id": os.getenv("TELEGRAM_CHAT_ID"), "caption": caption or ""},
			files={"photo": (filename, content, "image/png")},
			timeout=30,
		)
		if not r.ok:
			try:
				logger.warning("Telegram sendPhoto(bytes) failed | status=%s | body=%s", r.status_code, r.text[:300])
			except Exception:
				pass
			return None
		j = r.json()
		mid = (j.get("result") or {}).get("message_id")
		if mid is None:
			try:
				logger.warning("Telegram sendPhoto(bytes) no message_id | json=%s", str(j)[:300])
			except Exception:
				pass
		else:
			try:
				logger.info("Telegram sendPhoto(bytes) OK | chat_id=%s | message_id=%s", os.getenv("TELEGRAM_CHAT_ID"), str(mid))
			except Exception:
				pass
		return mid
	except Exception as e:
		try:
			logger.exception("Telegram sendPhoto(bytes) exception: %s", str(e)[:200])
		except Exception:
			pass
		return None
