FROM python:3.10-slim

WORKDIR /app

COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app .

COPY docker/gunicorn/gunicorn.conf.py /gunicorn.conf.py

CMD ["gunicorn", "-c", "/gunicorn.conf.py", "app:app"]
