import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logging() -> None:
	log_dir = os.path.join("instance", "logs")
	os.makedirs(log_dir, exist_ok=True)
	log_path = os.path.join(log_dir, "batch.log")

	root = logging.getLogger()
	if any(isinstance(h, RotatingFileHandler) for h in root.handlers):
		return  # already configured

	root.setLevel(logging.INFO)

	fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

	file_handler = RotatingFileHandler(log_path, maxBytes=2 * 1024 * 1024, backupCount=5, encoding="utf-8")
	file_handler.setLevel(logging.INFO)
	file_handler.setFormatter(fmt)
	root.addHandler(file_handler)

	console = logging.StreamHandler()
	console.setLevel(logging.INFO)
	console.setFormatter(fmt)
	root.addHandler(console)


def get_logger(name: str) -> logging.Logger:
	setup_logging()
	return logging.getLogger(name)
