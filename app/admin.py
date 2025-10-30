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
	# Trì hoãn import để tránh yêu cầu playwright khi chạy CLI/migrate
	from .services.checker import enqueue_accounts_check

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
		acc.can_login = False
		acc.total_orders = 0
		acc.last_checked_at = None
	db.session.commit()

	enqueue_accounts_check([email for email, _ in pairs])
	flash(f"Đã lưu {created} tài khoản mới. Batch kiểm tra đã được xếp hàng.", "success")
	return redirect(url_for("admin.dashboard"))


@admin_bp.post("/run-all")
def run_all():
	from .services.checker import enqueue_accounts_check
	emails = [a.email for a in Account.query.all()]
	if not emails:
		flash("Chưa có tài khoản nào để chạy.", "warning")
		return redirect(url_for("admin.dashboard"))
	enqueue_accounts_check(emails)
	flash(f"Đã xếp batch cho {len(emails)} tài khoản.", "success")
	return redirect(url_for("admin.dashboard"))
