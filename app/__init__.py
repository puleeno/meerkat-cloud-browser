from flask import Flask
from dotenv import load_dotenv
import os


def create_app() -> Flask:
	load_dotenv()
	app = Flask(__name__)

	# DB config (default SQLite if no DATABASE_URL)
	db_url = os.getenv("DATABASE_URL", "sqlite:///instance/app.db")
	app.config.from_mapping(
		SECRET_KEY=os.getenv("SECRET_KEY", "dev-secret"),
		ENV=os.getenv("FLASK_ENV", "development"),
		SQLALCHEMY_DATABASE_URI=db_url,
		SQLALCHEMY_TRACK_MODIFICATIONS=False,
		ADMIN_USERNAME=os.getenv("ADMIN_USERNAME", "admin"),
		ADMIN_PASSWORD=os.getenv("ADMIN_PASSWORD", "admin"),
	)

	# init extensions
	from .extensions import db, migrate
	db.init_app(app)
	migrate.init_app(app, db)

	# seed admin nếu ENV có và bảng đã tồn tại
	from sqlalchemy import inspect
	from .models import AdminUser
	from .security import hash_password
	with app.app_context():
		inspector = inspect(db.engine)
		if inspector.has_table("admin_users"):
			username = app.config.get("ADMIN_USERNAME")
			password = app.config.get("ADMIN_PASSWORD")
			if username and password:
				u = AdminUser.query.filter_by(username=username).one_or_none()
				if u is None:
					u = AdminUser(username=username, password_hash=hash_password(password))
					db.session.add(u)
					db.session.commit()

	# blueprints
	from .routes import main_bp
	app.register_blueprint(main_bp)
	from .auth_routes import auth_bp
	app.register_blueprint(auth_bp)
	from .admin import admin_bp
	app.register_blueprint(admin_bp, url_prefix="/admin")

	# CLI commands
	from .cli import register_cli
	register_cli(app)

	return app
