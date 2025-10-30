from flask import Blueprint, render_template, request, redirect, url_for, flash
from .auth import authenticate, logout


auth_bp = Blueprint("auth", __name__, template_folder="templates")


@auth_bp.get("/login")
def login():
	return render_template("login.html")


@auth_bp.post("/login")
def login_post():
	username = request.form.get("username", "").strip()
	password = request.form.get("password", "").strip()
	if not username or not password:
		flash("Thiếu username/mật khẩu", "warning")
		return redirect(url_for("auth.login"))
	if not authenticate(username, password):
		flash("Sai thông tin đăng nhập", "danger")
		return redirect(url_for("auth.login"))
	return redirect(url_for("admin.dashboard"))


@auth_bp.get("/logout")
def logout_get():
	logout()
	flash("Đã đăng xuất", "info")
	return redirect(url_for("auth.login"))
