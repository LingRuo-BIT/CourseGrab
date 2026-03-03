# -*- coding: utf-8 -*-
"""
FastAPI 应用入口
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from database import init_db
from routers import courses, queue, grabber, schedule, auth, settings, proxy


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化数据库
    await init_db()
    print("数据库初始化完成")
    yield
    # 关闭时清理
    print("应用关闭")


# 创建应用
app = FastAPI(
    title="CourseGrab",
    description="BIT 辅助抢课系统 API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router, prefix="/api")
app.include_router(courses.router, prefix="/api")
app.include_router(queue.router, prefix="/api")
app.include_router(grabber.router, prefix="/api")
app.include_router(schedule.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(proxy.router, prefix="/api")

# 静态文件服务
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")


@app.get("/")
async def root():
    """返回前端页面"""
    index_path = os.path.join(frontend_path, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "CourseGrab API", "docs": "/docs"}


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {"status": "ok"}
