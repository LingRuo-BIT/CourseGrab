# -*- coding: utf-8 -*-
"""
数据库模块
定义数据库连接和 ORM 模型
"""

import os
from datetime import datetime
from typing import Optional
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Text, DateTime, Float, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker as async_sessionmaker

from config import settings

# 确保 data 目录存在
data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
os.makedirs(data_dir, exist_ok=True)

# 创建异步引擎
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
)

# 创建异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# 基类
Base = declarative_base()


class Credential(Base):
    """用户凭证表"""
    __tablename__ = "credentials"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    cookies = Column(Text, nullable=False, comment="JSON格式的Cookie")
    csrf_token = Column(String(255), nullable=True, comment="CSRF Token")
    is_valid = Column(Boolean, default=True, comment="凭证是否有效")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class GrabTask(Base):
    """抢课任务表"""
    __tablename__ = "grab_queue"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    bjdm = Column(String(100), unique=True, nullable=False, comment="班级代码（唯一标识）")
    kcdm = Column(String(50), nullable=False, comment="课程代码（用于分组）")
    kcmc = Column(String(200), nullable=False, comment="课程名称")
    bjmc = Column(String(200), nullable=True, comment="班级名称")
    rkjs = Column(String(200), nullable=True, comment="任课教师")
    pksj = Column(String(500), nullable=True, comment="排课时间")
    pkdd = Column(String(200), nullable=True, comment="排课地点")
    xnxqmc = Column(String(100), nullable=True, comment="学年学期名称")
    kxrs = Column(Integer, nullable=True, comment="可选人数")
    dqrs = Column(Integer, nullable=True, comment="当前人数")
    priority = Column(Integer, default=0, comment="优先级")
    status = Column(String(20), default="pending", comment="状态: pending/grabbing/success/failed/cancelled")
    error_msg = Column(Text, nullable=True, comment="错误信息")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class SelectedCourse(Base):
    """已选课程缓存表"""
    __tablename__ = "selected_courses"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    bjdm = Column(String(100), unique=True, nullable=False, comment="班级代码")
    kcdm = Column(String(50), nullable=False, comment="课程代码")
    course_data = Column(Text, nullable=False, comment="JSON格式的完整课程数据")
    xnxqmc = Column(String(100), nullable=True, comment="学年学期名称")
    synced_at = Column(DateTime, default=datetime.now)


class NotificationConfig(Base):
    """通知配置表"""
    __tablename__ = "notification_config"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    # 邮件配置
    email_enabled = Column(Boolean, default=False)
    email_smtp_host = Column(String(200), nullable=True)
    email_smtp_port = Column(Integer, nullable=True)
    email_username = Column(String(200), nullable=True)
    email_password = Column(String(200), nullable=True)
    email_to = Column(String(500), nullable=True)
    # 企业微信配置
    wecom_enabled = Column(Boolean, default=False)
    wecom_webhook = Column(String(500), nullable=True)
    
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class Log(Base):
    """操作日志表"""
    __tablename__ = "logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    level = Column(String(20), nullable=False, comment="日志级别: INFO/WARNING/ERROR")
    module = Column(String(100), nullable=True, comment="模块名称")
    message = Column(Text, nullable=False, comment="日志内容")
    created_at = Column(DateTime, default=datetime.now)


async def init_db():
    """初始化数据库，创建所有表"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    """获取数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
