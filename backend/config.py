# -*- coding: utf-8 -*-
"""
配置管理模块
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """应用配置"""
    
    # 应用配置
    app_name: str = "CourseGrab"
    app_version: str = "1.0.0"
    debug: bool = True
    
    # 数据库配置
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/coursegrab.db",
        description="数据库连接URL"
    )
    
    # 选课系统配置
    bit_base_url: str = "https://xk.bit.edu.cn"
    bit_app_path: str = "/yjsxkapp/sys/xsxkappbit"
    
    # 请求配置
    request_timeout: int = 10
    request_retry_count: int = 3
    grab_interval: float = 0.3  # 抢课间隔（秒）
    csrf_refresh_interval: int = 120  # CSRF Token 刷新间隔（秒）
    
    # 代理配置
    proxy_host: str = "127.0.0.1"
    proxy_port: int = 8080
    
    # 邮件配置
    email_enabled: bool = False
    email_smtp_host: str = ""
    email_smtp_port: int = 465
    email_username: str = ""
    email_password: str = ""
    email_to: str = ""
    
    # 企业微信配置
    wecom_enabled: bool = False
    wecom_webhook: str = ""
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
    
    @property
    def api_base_url(self) -> str:
        """获取完整的 API 基础 URL"""
        return f"{self.bit_base_url}{self.bit_app_path}"


# 全局配置实例
settings = Settings()


def get_settings() -> Settings:
    """获取配置实例"""
    return settings
