# -*- coding: utf-8 -*-
"""
设置路由（通知配置等）
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db, NotificationConfig
from models import (
    ApiResponse,
    NotificationConfigUpdate,
    NotificationConfigResponse,
)
from services.notification import NotificationService

router = APIRouter(prefix="/settings", tags=["设置"])


@router.get("/notification", response_model=ApiResponse)
async def get_notification_config(
    db: AsyncSession = Depends(get_db),
):
    """
    获取通知配置
    """
    result = await db.execute(select(NotificationConfig).limit(1))
    config = result.scalar_one_or_none()
    
    if config:
        data = {
            "email_enabled": config.email_enabled,
            "email_smtp_host": config.email_smtp_host,
            "email_smtp_port": config.email_smtp_port,
            "email_username": config.email_username,
            "email_to": config.email_to,
            "wecom_enabled": config.wecom_enabled,
            "wecom_webhook": config.wecom_webhook,
        }
    else:
        data = {
            "email_enabled": False,
            "email_smtp_host": None,
            "email_smtp_port": None,
            "email_username": None,
            "email_to": None,
            "wecom_enabled": False,
            "wecom_webhook": None,
        }
    
    return ApiResponse(
        success=True,
        message="获取成功",
        data=data,
    )


@router.put("/notification", response_model=ApiResponse)
async def update_notification_config(
    config: NotificationConfigUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    更新通知配置
    """
    result = await db.execute(select(NotificationConfig).limit(1))
    existing = result.scalar_one_or_none()
    
    if existing:
        existing.email_enabled = config.email_enabled
        existing.email_smtp_host = config.email_smtp_host
        existing.email_smtp_port = config.email_smtp_port
        existing.email_username = config.email_username
        existing.email_password = config.email_password
        existing.email_to = config.email_to
        existing.wecom_enabled = config.wecom_enabled
        existing.wecom_webhook = config.wecom_webhook
    else:
        new_config = NotificationConfig(
            email_enabled=config.email_enabled,
            email_smtp_host=config.email_smtp_host,
            email_smtp_port=config.email_smtp_port,
            email_username=config.email_username,
            email_password=config.email_password,
            email_to=config.email_to,
            wecom_enabled=config.wecom_enabled,
            wecom_webhook=config.wecom_webhook,
        )
        db.add(new_config)
    
    await db.commit()
    
    return ApiResponse(
        success=True,
        message="配置更新成功",
    )


@router.post("/notification/test", response_model=ApiResponse)
async def test_notification(
    db: AsyncSession = Depends(get_db),
):
    """
    测试通知配置
    """
    result = await db.execute(select(NotificationConfig).limit(1))
    config = result.scalar_one_or_none()
    
    if not config:
        return ApiResponse(
            success=False,
            message="未配置通知",
        )
    
    # 创建通知服务
    email_config = None
    wecom_config = None
    
    if config.email_enabled:
        email_config = {
            "enabled": True,
            "smtp_host": config.email_smtp_host,
            "smtp_port": config.email_smtp_port,
            "username": config.email_username,
            "password": config.email_password,
            "to": config.email_to,
        }
    
    if config.wecom_enabled:
        wecom_config = {
            "enabled": True,
            "webhook": config.wecom_webhook,
        }
    
    service = NotificationService(
        email_config=email_config,
        wecom_config=wecom_config,
    )
    
    results = await service.test_notification()
    
    return ApiResponse(
        success=True,
        message="测试完成",
        data=results,
    )
