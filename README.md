# Meerkat Cloud Browser - Flask

Dự án Flask khởi tạo tối thiểu cho Windows.

## Yêu cầu
- Python 3.12.x (khuyến nghị). Tránh Python 3.13 do `greenlet` chưa có wheel tương thích trên Windows.
- (Khuyến nghị) PowerShell hoặc Git Bash

## Thiết lập nhanh (Windows PowerShell)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt

# (Tuỳ chọn) tạo file .env từ mẫu
copy env.example .env

# Cài Playwright browsers
python -m playwright install firefox

# Chạy server
python wsgi.py
```

Lưu ý: nếu máy bạn có nhiều phiên bản Python, hãy tạo môi trường với Python 3.12 cụ thể:
```powershell
py -3.12 -m venv .venv
```

## Thiết lập nhanh (Git Bash)
```bash
python -m venv .venv
source .venv/Scripts/activate
pip install --upgrade pip
pip install -r requirements.txt

# (Tuỳ chọn) tạo file .env từ mẫu
cp env.example .env

# Cài Playwright browsers
python -m playwright install firefox

# Chạy server
python wsgi.py
```

Nếu có nhiều phiên bản Python, tạo môi trường với 3.12 cụ thể:
```bash
py -3.12 -m venv .venv
```

Sau khi chạy, truy cập `http://127.0.0.1:5000/` để kiểm tra.

## Cấu trúc thư mục
```
app/
  __init__.py
  routes.py
  admin.py
  models.py
  services/
    checker.py
  templates/
    base.html
    dashboard.html
wsgi.py
requirements.txt
env.example
```

## Cấu hình Database (PostgreSQL/MySQL)
Ứng dụng dùng SQLAlchemy qua biến môi trường `DATABASE_URL`.
- Nếu KHÔNG đặt `DATABASE_URL`, mặc định dùng SQLite tại `instance/app.db`.
- PostgreSQL (khuyến nghị driver psycopg v3):
  - `DATABASE_URL=postgresql+psycopg://username:password@localhost:5432/dbname`
- MySQL (driver PyMySQL):
  - `DATABASE_URL=mysql+pymysql://username:password@localhost:3306/dbname`

Gợi ý tạo `.env`:
```
# PostgreSQL
# DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/meerkat

# MySQL
# DATABASE_URL=mysql+pymysql://user:pass@localhost:3306/meerkat
```

## Migrate DB
- PowerShell:
```powershell
$env:FLASK_APP="wsgi.py"
flask db init
flask db migrate -m "init db"
flask db upgrade
```
- Git Bash:
```bash
export FLASK_APP=wsgi.py
flask db init
flask db migrate -m "init db"
flask db upgrade
```

## Luồng kiểm tra tài khoản (Playwright -> Cookie -> Scrapy)
1. Playwright đăng nhập REI bằng Firefox, lưu cookie jar phiên vào storage.
2. Scrapy sử dụng cookie đã lưu để gọi endpoint lịch sử đơn theo từng năm (2014 → năm hiện tại), giảm thiểu tương tác trình duyệt và requests thừa.
3. Kết quả được lưu về DB theo từng năm và tổng đơn hàng, kèm trạng thái đăng nhập.

## Ghi chú
- Biến môi trường `SECRET_KEY` sẽ mặc định là `dev-secret` nếu không đặt trong `.env`.
- `FLASK_ENV=development` bật debug; không dùng debug ở môi trường production.
- PostgreSQL cần package `psycopg[binary]`; MySQL dùng `PyMySQL` (không cần compiler trên Windows).
