import json
import os
from typing import Any, List


def _ensure_dir(path: str) -> None:
	os.makedirs(path, exist_ok=True)


def _safe_key(email: str) -> str:
	return (
		email.lower()
		.replace("@", "_at_")
		.replace("/", "_")
		.replace("\\", "_")
	)


def get_session_path() -> str:
	return os.path.join("instance", "sessions")


def save_cookies(email: str, cookies: List[dict[str, Any]]) -> str:
	sessions_dir = get_session_path()
	_ensure_dir(sessions_dir)
	key = _safe_key(email)
	file_path = os.path.join(sessions_dir, f"{key}.json")
	with open(file_path, "w", encoding="utf-8") as f:
		json.dump(cookies, f, ensure_ascii=False, indent=2)
	return file_path


def load_cookies(email: str) -> List[dict[str, Any]]:
	key = _safe_key(email)
	file_path = os.path.join(get_session_path(), f"{key}.json")
	if not os.path.exists(file_path):
		return []
	with open(file_path, "r", encoding="utf-8") as f:
		return json.load(f)
