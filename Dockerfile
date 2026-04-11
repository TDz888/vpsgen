# Dockerfile - Đặt ở thư mục GỐC của repository
FROM python:3.11-slim

WORKDIR /app

# Copy requirements từ thư mục backend
COPY backend/requirements.txt .

# Cài đặt dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ code
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Mở cổng (Back4App thường dùng cổng 8080)
EXPOSE 8080

# Chạy ứng dụng
CMD ["gunicorn", "--chdir", "./backend", "-b", "0.0.0.0:8080", "app:app"]
