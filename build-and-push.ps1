# =========================================================
# build-and-push.ps1
# Script tự động build và push AITutor images lên Docker Hub
# Cách dùng: .\build-and-push.ps1 [-Tag "v1.0"]
# =========================================================

param(
    [string]$Tag = "latest"
)

$DockerHubUser = "vuquockhai"
$AiImageName   = "$DockerHubUser/aitutor-ai-api"
$SpringImageName = "$DockerHubUser/aitutor-spring-api"

Write-Host ""
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "  AITutor Docker Build & Push Script" -ForegroundColor Cyan
Write-Host "  Tag: $Tag" -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host ""

# --- Bước 1: Đăng nhập Docker Hub ---
Write-Host "[1/5] Dang nhap Docker Hub..." -ForegroundColor Yellow
docker login
if ($LASTEXITCODE -ne 0) {
    Write-Host "FAILED: Dang nhap Docker Hub that bai!" -ForegroundColor Red
    exit 1
}

# --- Bước 2: Build AI API image ---
Write-Host ""
Write-Host "[2/5] Build AI API image (Python/FastAPI)..." -ForegroundColor Yellow
Write-Host "      Image: ${AiImageName}:${Tag}" -ForegroundColor Gray
Write-Host "      (Lan dau co the mat 30-60 phut do cai torch, tensorflow...)" -ForegroundColor Gray
docker build -t "${AiImageName}:${Tag}" ./AI
if ($LASTEXITCODE -ne 0) {
    Write-Host "FAILED: Build AI API image that bai!" -ForegroundColor Red
    exit 1
}
Write-Host "OK: AI API image da build thanh cong!" -ForegroundColor Green

# --- Bước 3: Build Spring API image ---
Write-Host ""
Write-Host "[3/5] Build Spring API image (Java/Gradle)..." -ForegroundColor Yellow
Write-Host "      Image: ${SpringImageName}:${Tag}" -ForegroundColor Gray
docker build -t "${SpringImageName}:${Tag}" ./ai-elearning
if ($LASTEXITCODE -ne 0) {
    Write-Host "FAILED: Build Spring API image that bai!" -ForegroundColor Red
    exit 1
}
Write-Host "OK: Spring API image da build thanh cong!" -ForegroundColor Green

# --- Bước 4: Push lên Docker Hub ---
Write-Host ""
Write-Host "[4/5] Push images len Docker Hub..." -ForegroundColor Yellow

Write-Host "      Pushing ${AiImageName}:${Tag}..." -ForegroundColor Gray
docker push "${AiImageName}:${Tag}"
if ($LASTEXITCODE -ne 0) {
    Write-Host "FAILED: Push AI API image that bai!" -ForegroundColor Red
    exit 1
}

Write-Host "      Pushing ${SpringImageName}:${Tag}..." -ForegroundColor Gray
docker push "${SpringImageName}:${Tag}"
if ($LASTEXITCODE -ne 0) {
    Write-Host "FAILED: Push Spring API image that bai!" -ForegroundColor Red
    exit 1
}

# --- Bước 5: Tóm tắt ---
Write-Host ""
Write-Host "[5/5] Hoan tat!" -ForegroundColor Green
Write-Host ""
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "  Images da duoc push len Docker Hub:" -ForegroundColor Cyan
Write-Host "  - docker pull ${AiImageName}:${Tag}" -ForegroundColor White
Write-Host "  - docker pull ${SpringImageName}:${Tag}" -ForegroundColor White
Write-Host ""
Write-Host "  Docker Hub: https://hub.docker.com/u/$DockerHubUser" -ForegroundColor White
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host ""

# Hiển thị kích thước images
Write-Host "Kich thuoc cac images:" -ForegroundColor Yellow
docker images | Select-String "aitutor"
