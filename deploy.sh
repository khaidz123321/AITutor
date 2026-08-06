#!/bin/bash
# ==============================================
# deploy.sh - Script deploy AITutor lên server Linux
# Chạy lần đầu: bash deploy.sh --init
# Chạy update:  bash deploy.sh
# ==============================================

set -e  # Dừng nếu có lỗi

DOCKER_USER="vuquockhai"
APP_DIR="/app/aitutor"

echo ""
echo "=============================================="
echo "  AITutor Deploy Script"
echo "=============================================="

# --- Cài Docker nếu chưa có (Ubuntu/Debian) ---
if ! command -v docker &> /dev/null; then
    echo "[!] Docker chưa được cài. Đang cài đặt..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
    echo "[+] Docker đã cài xong!"
fi

# --- Tạo cấu trúc thư mục ---
if [ "$1" == "--init" ]; then
    echo "[1/4] Tạo thư mục..."
    mkdir -p $APP_DIR/AI/multilingual-e5-large-finetuned
    mkdir -p $APP_DIR/AI/uploads
    mkdir -p $APP_DIR/AI/data/vector_db

    echo ""
    echo "[!] QUAN TRỌNG: Bạn cần tạo 2 file .env trước khi chạy tiếp:"
    echo ""
    echo "  1. $APP_DIR/.env  (password postgres & spring config)"
    echo "     POSTGRES_USER=postgres"
    echo "     POSTGRES_PASSWORD=your_strong_password"
    echo "     POSTGRES_DB=ai_elearning_db"
    echo "     JWT_SECRET=your_super_secret_jwt_key_here"
    echo "     CORS_ALLOWED_ORIGINS=https://app.yourdomain.com"
    echo ""
    echo "  2. $APP_DIR/AI/.env  (API keys)"
    echo "     (copy từ AI/.env.example và điền keys thật)"
    echo ""
    echo "  3. Copy model lên server:"
    echo "     scp -r ./AI/multilingual-e5-large-finetuned user@server:$APP_DIR/AI/"
    echo ""
    echo "Sau đó chạy lại: bash deploy.sh"
    exit 0
fi

# --- Kiểm tra file .env ---
if [ ! -f "$APP_DIR/.env" ]; then
    echo "[ERROR] Thiếu file $APP_DIR/.env!"
    echo "Chạy: bash deploy.sh --init để xem hướng dẫn"
    exit 1
fi

if [ ! -f "$APP_DIR/AI/.env" ]; then
    echo "[ERROR] Thiếu file $APP_DIR/AI/.env!"
    exit 1
fi

# --- Pull images mới nhất ---
echo "[2/4] Pull images từ Docker Hub..."
docker pull $DOCKER_USER/aitutor-ai-api:latest
docker pull $DOCKER_USER/aitutor-spring-api:latest

# --- Restart services ---
echo "[3/4] Khởi động lại services..."
cd $APP_DIR
docker compose down
docker compose up -d

# --- Kiểm tra ---
echo "[4/4] Kiểm tra trạng thái..."
sleep 5
docker compose ps

echo ""
echo "=============================================="
echo "  Deploy hoàn tất!"
echo "  AI API:     http://$(hostname -I | awk '{print $1}'):8001/docs"
echo "  Spring API: http://$(hostname -I | awk '{print $1}'):8080"
echo "=============================================="
