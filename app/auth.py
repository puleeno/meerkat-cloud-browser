from __future__ import annotations
from flask import current_app, request, Response, session, redirect, url_for
from typing import Callable, Any
from .models import AdminUser
from .security import verify_password


def login_required(fn: Callable[..., Any]) -> Callable[..., Any]:
	def wrapper(*args, **kwargs):
		if not session.get("admin_user_id"):
			return redirect(url_for("auth.login"))
		return fn(*args, **kwargs)
	return wrapper


def authenticate(username: str, password: str) -> bool:
	user = AdminUser.query.filter_by(username=username).one_or_none()
	if user and verify_password(user.password_hash, password):
		session["admin_user_id"] = user.id
		return True
	return False


def logout() -> None:
	session.pop("admin_user_id", None)
