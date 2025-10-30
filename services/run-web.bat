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
flask run  >> instance\logs\webs.log 2>&1

endlocal
