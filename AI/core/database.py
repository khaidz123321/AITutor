"""
Tạo ống kết nối dtb
"""
from sqlalchemy import create_engine 
from core.config import settings 

engine = create_engine(
    settings.DATABASE_URL, 
    pool_pre_ping = True,
    pool_recycle = 3600,   # Recycle connections after 1 hour
    pool_timeout = 30      # Timeout if connection isn't available in 30s
)