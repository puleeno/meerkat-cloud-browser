from datetime import datetime
from .extensions import db


class Account(db.Model):
	__tablename__ = "accounts"

	id = db.Column(db.Integer, primary_key=True)
	email = db.Column(db.String(255), unique=True, nullable=False)
	password = db.Column(db.String(255), nullable=False)
	can_login = db.Column(db.Boolean, nullable=True)  # null = chưa kiểm tra
	total_orders = db.Column(db.Integer, nullable=False, default=0)
	last_checked_at = db.Column(db.DateTime)
	created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
	cookies_json = db.Column(db.Text)  # lưu cookie jar dạng JSON
	headers_json = db.Column(db.Text)  # lưu request headers dùng khi login
	error_message = db.Column(db.Text)  # lưu thông báo lỗi (ví dụ từ .sr-only)
	# Lưu URL Telegram thay vì chỉ message_id
	after_login_telegram_message_url = db.Column(db.Text)
	stats_status_telegram_message_url = db.Column(db.Text)
	# Phân loại lỗi đăng nhập: 'credentials', 'proxy', 'blocked', 'unknown'
	login_failure_type = db.Column(db.String(32))

	stats = db.relationship("AccountYearStat", backref="account", lazy=True, cascade="all, delete-orphan")


class AccountYearStat(db.Model):
	__tablename__ = "account_year_stats"

	id = db.Column(db.Integer, primary_key=True)
	account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False)
	year = db.Column(db.Integer, nullable=False)
	orders_count = db.Column(db.Integer, nullable=False, default=0)
	raw_json = db.Column(db.Text)  # lưu toàn bộ response JSON theo năm
	created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

	__table_args__ = (
		db.UniqueConstraint("account_id", "year", name="uq_account_year"),
	)


class AdminUser(db.Model):
	__tablename__ = "admin_users"

	id = db.Column(db.Integer, primary_key=True)
	username = db.Column(db.String(150), unique=True, nullable=False)
	password_hash = db.Column(db.String(255), nullable=False)
	created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
