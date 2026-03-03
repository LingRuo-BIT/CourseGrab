# -*- coding: utf-8 -*-
"""
抢课控制路由
"""

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import asyncio
import json

from database import get_db
from models import (
    GrabStartRequest,
    GrabStopRequest,
    GrabberStatus,
    ApiResponse,
)
from services.grabber_engine import get_grabber_engine

router = APIRouter(prefix="/grabber", tags=["抢课控制"])

# WebSocket 连接管理
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()


@router.post("/start", response_model=ApiResponse)
async def start_grabbing(
    request: GrabStartRequest = None,
    db: AsyncSession = Depends(get_db),
):
    """
    开始抢课
    """
    engine = get_grabber_engine()
    
    task_ids = request.task_ids if request else None
    result = await engine.start(task_ids)
    
    # 广播状态更新
    await manager.broadcast({
        "type": "status_update",
        "data": engine.get_status()
    })
    
    return ApiResponse(
        success=result["success"],
        message=result["message"],
        data=result,
    )


@router.post("/stop", response_model=ApiResponse)
async def stop_grabbing(
    request: GrabStopRequest = None,
    db: AsyncSession = Depends(get_db),
):
    """
    停止抢课
    """
    engine = get_grabber_engine()
    
    task_ids = request.task_ids if request else None
    result = await engine.stop(task_ids)
    
    # 广播状态更新
    await manager.broadcast({
        "type": "status_update",
        "data": engine.get_status()
    })
    
    return ApiResponse(
        success=result["success"],
        message=result["message"],
        data=result,
    )


@router.get("/status", response_model=ApiResponse)
async def get_status():
    """
    获取抢课状态
    """
    engine = get_grabber_engine()
    status = engine.get_status()
    
    return ApiResponse(
        success=True,
        message="获取成功",
        data=status,
    )


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket 实时推送
    """
    await manager.connect(websocket)
    
    engine = get_grabber_engine()
    
    # 注册成功回调
    def on_success(bjdm, kcdm, kcmc):
        asyncio.create_task(manager.broadcast({
            "type": "grab_success",
            "data": {
                "bjdm": bjdm,
                "kcdm": kcdm,
                "kcmc": kcmc,
            }
        }))
    
    engine.on_success(on_success)
    
    try:
        # 发送初始状态
        await websocket.send_json({
            "type": "connected",
            "data": engine.get_status()
        })
        
        # 定时发送状态更新
        while True:
            await asyncio.sleep(2)
            await websocket.send_json({
                "type": "status_update",
                "data": engine.get_status()
            })
    except WebSocketDisconnect:
        manager.disconnect(websocket)
