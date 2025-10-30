# Meerkat Cloud Browser - Flask

Dự án Flask khởi tạo tối thiểu cho Windows.

## Yêu cầu
- Python 3.10+ đã cài đặt và có `python`/`pip` trong PATH
- (Khuyến nghị) PowerShell hoặc Git Bash

## Thiết lập nhanh (Windows PowerShell)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt

# (Tuỳ chọn) tạo file .env từ mẫu
copy env.example .env

# Chạy server
python wsgi.py
```

## Thiết lập nhanh (Git Bash)
```bash
python -m venv .venv
source .venv/Scripts/activate
pip install --upgrade pip
pip install -r requirements.txt

# (Tuỳ chọn) tạo file .env từ mẫu
cp env.example .env

# Chạy server
python wsgi.py
```

Sau khi chạy, truy cập `http://127.0.0.1:5000/` để kiểm tra.

## Cấu trúc thư mục
```
app/
  __init__.py
  routes.py
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

## Ghi chú
- Biến môi trường `SECRET_KEY` sẽ mặc định là `dev-secret` nếu không đặt trong `.env`.
- `FLASK_ENV=development` bật debug; không dùng debug ở môi trường production.
- PostgreSQL cần package `psycopg[binary]`; MySQL dùng `PyMySQL` (không cần compiler trên Windows).
