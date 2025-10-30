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


def send_message(text: str) -> None:
	if not _enabled():
		return
	try:
		requests.post(
			f"{_base_url()}/sendMessage",
			data={"chat_id": os.getenv("TELEGRAM_CHAT_ID"), "text": text},
			timeout=15,
		)
	except Exception:
		pass


def send_photo(photo_path: str, caption: Optional[str] = None) -> None:
	if not _enabled():
		return
	try:
		with open(photo_path, "rb") as f:
			requests.post(
				f"{_base_url()}/sendPhoto",
				data={"chat_id": os.getenv("TELEGRAM_CHAT_ID"), "caption": caption or ""},
				files={"photo": f},
				timeout=30,
			)
	except Exception:
		pass
