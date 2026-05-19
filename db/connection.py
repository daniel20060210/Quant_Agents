import pymysql
from .config import DB_CONFIG


def get_connection():
    """获取 MySQL 数据库连接，使用 db/config.py 中的 DB_CONFIG。"""
    return pymysql.connect(**DB_CONFIG)
