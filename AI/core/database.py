"""
Tạo ống kết nối dtb
"""
from sqlalchemy import create_engine 
from core.config import settings 

engine = create_engine(
    settings.DATABASE_URL, 
    pool_pre_ping =  True
)