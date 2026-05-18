import pymysql
from .config import DB_CONFIG


def get_connection():
    """获取 MySQL 数据库连接"""
    return pymysql.connect(**DB_CONFIG)
