from flask import Flask
from dotenv import load_dotenv
import os


def create_app() -> Flask:
	load_dotenv()
	app = Flask(__name__)
	app.config.from_mapping(
		SECRET_KEY=os.getenv("SECRET_KEY", "dev-secret"),
		ENV=os.getenv("FLASK_ENV", "development"),
	)

	from .routes import main_bp
	app.register_blueprint(main_bp)
	return app
