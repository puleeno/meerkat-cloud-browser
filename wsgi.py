import sys, asyncio

from app import create_app

app = create_app()

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

if __name__ == "__main__":
	app.run(host="127.0.0.1", port=5000, debug=True)
