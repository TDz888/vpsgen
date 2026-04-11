# 1. Chọn base image chính thức từ Python
FROM python:3.11-slim

# 2. Đặt thư mục làm việc trong container
WORKDIR /app

# 3. Sao chép file requirements và cài đặt dependencies
# - Làm vậy để tận dụng cơ chế cache của Docker, tăng tốc build
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Sao chép toàn bộ mã nguồn của backend và frontend
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# 5. (Khuyến nghị) Khai báo cổng ứng dụng sẽ lắng nghe
# Back4App sử dụng cổng 8080 cho container
EXPOSE 8080

# 6. Định nghĩa lệnh khởi động ứng dụng
# `--chdir` để chạy lệnh từ thư mục backend
# `-b 0.0.0.0:8080` để lắng nghe trên cổng 8080
# `app:app` có nghĩa là file `app.py` và biến `app` bên trong
CMD ["gunicorn", "--chdir", "./backend", "-b", "0.0.0.0:8080", "app:app"]
