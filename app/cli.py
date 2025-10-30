import click
from flask import current_app
from .extensions import db
from .models import Account


@click.command("check-accounts")
@click.option("--email", "emails", multiple=True, help="Email tài khoản cần check (có thể lặp). Mặc định: tất cả")
@click.option("--sync/--async", "sync_mode", default=False, help="Chạy đồng bộ (blocking) thay vì xếp batch nền")
def check_accounts_command(emails: tuple[str, ...], sync_mode: bool):
	"""Kiểm tra tài khoản (toàn bộ hoặc theo danh sách email)."""
	from .services.checker import enqueue_accounts_check, run_accounts_check_sync

	with current_app.app_context():
		lst = list(emails) if emails else [a.email for a in Account.query.all()]
		if not lst:
			click.echo("Không có tài khoản để chạy.")
			return
		if sync_mode:
			run_accounts_check_sync(lst)
			click.echo(f"Đã chạy xong {len(lst)} tài khoản.")
		else:
			enqueue_accounts_check(lst)
			click.echo(f"Đã xếp batch cho {len(lst)} tài khoản.")


def register_cli(app):
	app.cli.add_command(check_accounts_command)
