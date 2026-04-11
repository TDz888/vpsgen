#!/bin/bash
# start.sh - Khởi động backend

echo "========================================="
echo "🚀 Khởi động Singularity Club Backend"
echo "========================================="

# Tạo thư mục logs
mkdir -p logs

cd backend

# Cài dependencies
pip install -r requirements.txt

# Chạy app
python3 app.py
