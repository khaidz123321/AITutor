FROM python:3.12-slim

WORKDIR /app

# Cài đặt các thư viện hệ thống cần thiết cho một số package như psycopg2 và mysqlclient
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    pkg-config \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8001

CMD ["uvicorn", "API:app", "--host", "0.0.0.0", "--port", "8001"]
