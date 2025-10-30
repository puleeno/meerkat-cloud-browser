import io
from flask import Blueprint, render_template, request, redirect, url_for, flash
from .extensions import db
from .models import Account
from .auth import login_required


admin_bp = Blueprint("admin", __name__, template_folder="templates")


@admin_bp.before_request
@login_required
def _admin_auth_guard():
	pass


def parse_accounts(lines):
	pairs = []
	for raw in lines:
		line = raw.strip()
		if not line or line.startswith("#"):
			continue
		if ":" not in line:
			continue
		email, password = line.split(":", 1)
		email = email.strip()
		password = password.strip()
		if email and password:
			pairs.append((email, password))
	return pairs


@admin_bp.get("/dashboard")
def dashboard():
	accounts = Account.query.order_by(Account.created_at.desc()).all()
	return render_template("dashboard.html", accounts=accounts)


@admin_bp.post("/upload")
def upload_accounts():
	content = request.form.get("accounts_text", "")
	file = request.files.get("accounts_file")

	lines = []
	if content:
		lines.extend(content.splitlines())
	if file and file.filename:
		text = io.TextIOWrapper(file.stream, encoding="utf-8", errors="ignore").read()
		lines.extend(text.splitlines())

	pairs = parse_accounts(lines)
	if not pairs:
		flash("Không tìm thấy tài khoản hợp lệ.", "warning")
		return redirect(url_for("admin.dashboard"))

	created = 0
	for email, password in pairs:
		acc = Account.query.filter_by(email=email).one_or_none()
		if acc is None:
			acc = Account(email=email, password=password)
			db.session.add(acc)
			created += 1
		else:
			acc.password = password
		# Để can_login = NULL (chưa kiểm tra)
		acc.can_login = None
		acc.total_orders = 0
		acc.last_checked_at = None
	db.session.commit()

	flash(f"Đã lưu {created} tài khoản mới. Bạn có thể chạy batch từ nút 'Chạy batch tất cả tài khoản' hoặc CLI.", "success")
	return redirect(url_for("admin.dashboard"))


@admin_bp.post("/run-all")
def run_all():
	from .services.checker import enqueue_accounts_check
	# Chỉ chạy các tài khoản chưa kiểm tra (can_login IS NULL)
	emails = [a.email for a in Account.query.filter(Account.can_login.is_(None)).all()]
	if not emails:
		flash("Không có tài khoản nào cần chạy (tất cả đã được kiểm tra).", "info")
		return redirect(url_for("admin.dashboard"))
	enqueue_accounts_check(emails)
	flash(f"Đã xếp batch cho {len(emails)} tài khoản (chưa kiểm tra).", "success")
	return redirect(url_for("admin.dashboard"))
