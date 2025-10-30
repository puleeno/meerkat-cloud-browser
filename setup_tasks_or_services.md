cách “set up task” trên Windows để tự động chạy batch cho dự án (không cần mở IDE):
1) Chuẩn bị một file .bat để chạy batch
Ví dụ: C:\Users\puleeno\Projects\meerkat-cloud-browser\run_check_accounts.bat


Nội dung:
```
@echo off
setlocal
cd /d C:\Users\puleeno\Projects\meerkat-cloud-browser

REM Kích hoạt venv
call .venv\Scripts\activate

REM Biến môi trường khuyến nghị khi chạy nền
set FLASK_APP=wsgi.py
set PLAYWRIGHT_HEADLESS=1
set PLAYWRIGHT_KEEP_OPEN=0

REM Tuỳ chọn (giảm thời gian treo do proxy)
REM set PROXY_CHECK_ENABLED=1
REM set PROXY_CHECK_MAX_TRIES=5
REM set PROXY_CHECK_TIMEOUT=2

REM Tạo thư mục log nếu chưa có
if not exist instance\logs mkdir instance\logs

REM Chạy batch đồng bộ và ghi log
flask check-accounts --sync >> instance\logs\task_runner.log 2>&1

endlocal
```


Lần đầu hoặc khi cập nhật requirements:

```
@echo off
cd /d C:\Users\puleeno\Projects\meerkat-cloud-browser
call .venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install firefox
```

2) Tạo Task bằng Task Scheduler (GUI)
Mở “Task Scheduler” → Create Task…
General:
Name: Meerkat Batch Check
Run whether user is logged on or not, tick “Run with highest privileges”
Triggers: New… (Daily/Hourly/At startup tuỳ bạn)
Actions: New…
Action: Start a program
Program/script: C:\Windows\System32\cmd.exe
Add arguments: /c "C:\Users\puleeno\Projects\meerkat-cloud-browser\run_check_accounts.bat"
Start in: C:\Users\puleeno\Projects\meerkat-cloud-browser
Conditions: bỏ “Start the task only if the computer is on AC power” nếu cần
Settings: Enable “Stop the task if it runs longer than” (ví dụ 2 hours), “If the task fails, restart every 15 minutes up to 3 times”

3) Tạo Task bằng lệnh (không cần GUI)
Chạy trong PowerShell/Command Prompt (Run as Administrator):

```
schtasks /Create ^
 /TN "Meerkat Batch Check" ^
 /TR "C:\Windows\System32\cmd.exe /c \"C:\Users\puleeno\Projects\meerkat-cloud-browser\run_check_accounts.bat\"" ^
 /SC HOURLY /MO 1 ^
 /ST 09:00 ^
 /RL HIGHEST ^
 /F
 ```
/SC HOURLY /MO 1: chạy mỗi giờ; đổi /SC DAILY /ST 02:00 nếu muốn chạy mỗi ngày 02:00.
/RL HIGHEST: chạy quyền cao.
Xem chi tiết/log: instance\logs\task_runner.log

4) Lưu ý vận hành
.env phải đầy đủ (Telegram, DB, proxy). Nếu dùng proxy xoay vòng:
PROXY_LIST_PATH=proxy.txt
PROXY_SCHEME=http (hoặc socks5/socks5h)
PROXY_CHECK_SCHEME=http
PROXY_CHECK_ENABLED=1, PROXY_CHECK_TIMEOUT=2, PROXY_CHECK_MAX_TRIES=5
Khi chạy nền, tránh treo: PLAYWRIGHT_HEADLESS=1, PLAYWRIGHT_KEEP_OPEN=0
Log tổng: instance\logs\batch.log (file xoay vòng) + instance\logs\task_runner.log (log của task .bat)
Nếu lần chạy đầu bị lỗi Playwright browser chưa cài, chạy script cài Firefox như ở bước 1 một lần.