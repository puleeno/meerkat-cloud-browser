import os
import time
import requests
from typing import Optional


def _enabled() -> bool:
	token = os.getenv("TELEGRAM_BOT_TOKEN")
	chat_id = os.getenv("TELEGRAM_CHAT_ID")
	return bool(token and chat_id and os.getenv("TELEGRAM_ENABLED", "1") not in ("0", "false", "no"))


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
		j = r.json() if r.ok else {}
		return (j.get("result") or {}).get("message_id")
	except Exception:
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
			j = r.json() if r.ok else {}
			return (j.get("result") or {}).get("message_id")
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
		j = r.json() if r.ok else {}
		return (j.get("result") or {}).get("message_id")
	except Exception:
		return None
