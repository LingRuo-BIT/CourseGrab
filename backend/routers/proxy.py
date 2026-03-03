# -*- coding: utf-8 -*-
"""
代理相关路由
"""

from fastapi import APIRouter, Query
from models import ApiResponse
from services.proxy_manager import proxy_manager

router = APIRouter(prefix="/proxy", tags=["代理"])


@router.post("/start", response_model=ApiResponse)
async def start_proxy(
    port: int = Query(8888, ge=1024, le=65535, description="代理端口"),
):
    """
    启动代理服务
    """
    result = proxy_manager.start(port)
    
    return ApiResponse(
        success=result.get("success", False),
        message=result.get("message", ""),
        data={
            "port": result.get("port"),
            "instructions": result.get("instructions", []),
        } if result.get("success") else None
    )


@router.post("/stop", response_model=ApiResponse)
async def stop_proxy():
    """
    停止代理服务
    """
    result = proxy_manager.stop()
    
    return ApiResponse(
        success=result.get("success", False),
        message=result.get("message", ""),
    )


@router.get("/status", response_model=ApiResponse)
async def get_proxy_status():
    """
    获取代理状态
    """
    status = proxy_manager.get_status()
    
    return ApiResponse(
        success=True,
        message="运行中" if status.get("is_running") else "未运行",
        data=status,
    )
