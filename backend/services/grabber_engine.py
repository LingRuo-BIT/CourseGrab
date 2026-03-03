# -*- coding: utf-8 -*-
"""
抢课引擎
管理多线程抢课任务
"""

import asyncio
import json
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from database import GrabTask, Credential, SelectedCourse, AsyncSessionLocal
from services.api_client import BitApiClient
from services.notification import NotificationService
from config import settings


class GrabberEngine:
    """抢课引擎"""
    
    def __init__(self):
        self.is_running = False
        self.active_tasks: Dict[str, asyncio.Task] = {}  # bjdm -> Task
        self.success_count = 0
        self.failed_count = 0
        self._success_callbacks: List[Callable] = []
        self._csrf_refresh_task: Optional[asyncio.Task] = None
        self._notification_service: Optional[NotificationService] = None
        
        # 课程代码到成功班级的映射，用于同一课程成功后取消其他班级
        self._success_kcdm: Dict[str, str] = {}  # kcdm -> bjdm
    
    def on_success(self, callback: Callable):
        """注册成功回调"""
        self._success_callbacks.append(callback)
    
    def set_notification_service(self, service: NotificationService):
        """设置通知服务"""
        self._notification_service = service
    
    async def _get_tasks_to_grab(self, db: AsyncSession, task_ids: Optional[List[int]] = None) -> List[GrabTask]:
        """获取待抢课程列表"""
        query = select(GrabTask).where(
            GrabTask.status.in_(["pending", "grabbing"])
        )
        if task_ids:
            query = query.where(GrabTask.id.in_(task_ids))
        
        result = await db.execute(query)
        return list(result.scalars().all())
    
    async def _grab_single_course(self, bjdm: str, kcdm: str, kcmc: str, task_info: dict):
        """
        单个课程的抢课循环
        """
        attempt_count = 0
        last_error = ""
        
        while self.is_running:
            attempt_count += 1
            
            # 检查同门课是否已成功
            if kcdm in self._success_kcdm and self._success_kcdm[kcdm] != bjdm:
                print(f"[{kcmc}] 同门课程已抢到，取消此班级")
                await self._update_task_status(bjdm, "cancelled", "同门课程已选中其他班级")
                return
            
            async with AsyncSessionLocal() as db:
                try:
                    client = BitApiClient(db)
                    result = await client.choose_course(bjdm)
                    
                    code = result.get("code", -1)
                    msg = result.get("msg", "未知错误")
                    
                    if code == 1:
                        # code=1 只表示请求成功，需要验证是否真正选中
                        print(f"[{kcmc}] [PENDING] 收到响应 code=1，正在验证是否选中...")
                        
                        # 查询已选课程列表验证
                        is_selected = await self._verify_course_selected(client, bjdm)
                        
                        if is_selected:
                            # 真正选中了
                            print(f"[{kcmc}] [SUCCESS] 验证成功，已选中! (第{attempt_count}次尝试)")
                            self.success_count += 1
                            self._success_kcdm[kcdm] = bjdm
                            
                            await self._update_task_status(bjdm, "success", f"第{attempt_count}次尝试成功")
                            
                            # 发送通知
                            if self._notification_service:
                                await self._notification_service.notify_grab_success(
                                    kcmc=kcmc,
                                    bjmc=task_info.get("bjmc", ""),
                                    rkjs=task_info.get("rkjs", ""),
                                    pksj=task_info.get("pksj", ""),
                                    pkdd=task_info.get("pkdd", ""),
                                )
                            
                            # 触发回调
                            for callback in self._success_callbacks:
                                try:
                                    callback(bjdm, kcdm, kcmc)
                                except Exception as e:
                                    print(f"回调执行失败: {e}")
                            
                            return
                        else:
                            # 未选中，继续尝试
                            print(f"[{kcmc}] [FAIL] 验证失败，未在已选列表中找到")
                            last_error = "验证失败：未在已选课程中找到"
                    else:
                        # 抢课失败，继续尝试
                        last_error = msg
                        print(f"[{kcmc}] [FAIL] 第{attempt_count}次尝试: {msg}")
                    
                    # 每10次尝试更新一次状态
                    if attempt_count % 10 == 0:
                        await self._update_task_status(
                            bjdm, 
                            "grabbing", 
                            f"已尝试{attempt_count}次 - {last_error[:50] if last_error else ''}"
                        )
                        
                except Exception as e:
                    last_error = str(e)
                    print(f"[{kcmc}] [ERROR] 第{attempt_count}次尝试异常: {e}")
            
            # 等待指定间隔
            await asyncio.sleep(settings.grab_interval)
    
    async def _verify_course_selected(self, client: BitApiClient, bjdm: str) -> bool:
        """
        验证课程是否真正被选中
        通过查询已选课程列表，检查是否存在该课程且状态有效
        """
        try:
            courses = await client.get_selected_courses()
            
            for c in courses:
                if c.get("BJDM") == bjdm:
                    # 检查状态：SFYXXKJG=0 表示正式选中，SFYXXKJG=1 且 SFXZ=1 表示抽中
                    sfyxxkjg = c.get("SFYXXKJG")
                    sfxz = c.get("SFXZ")
                    
                    if sfyxxkjg == 0:
                        return True  # 正式选中
                    elif sfyxxkjg == 1 and sfxz == 1:
                        return True  # 抽中（待入库）
            
            return False
        except Exception as e:
            print(f"[验证] 查询已选课程失败: {e}")
            return False
    
    async def _update_task_status(
        self,
        bjdm: str,
        status: str,
        error_msg: Optional[str] = None
    ):
        """更新任务状态"""
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(GrabTask)
                .where(GrabTask.bjdm == bjdm)
                .values(
                    status=status,
                    error_msg=error_msg,
                    updated_at=datetime.now()
                )
            )
            await db.commit()
    
    async def _refresh_csrf_loop(self):
        """定时刷新 CSRF Token"""
        while self.is_running:
            try:
                async with AsyncSessionLocal() as db:
                    client = BitApiClient(db)
                    token = await client.fetch_csrf_token()
                    if token:
                        print(f"[CSRF] Token 已刷新: {token[:20]}...")
            except Exception as e:
                print(f"[CSRF] 刷新失败: {e}")
            
            await asyncio.sleep(settings.csrf_refresh_interval)
    
    async def _init_notification_service(self):
        """从数据库加载通知配置并初始化通知服务"""
        from database import NotificationConfig
        from sqlalchemy import select
        
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(NotificationConfig).limit(1))
                config = result.scalar_one_or_none()
                
                if not config:
                    print("[通知] 未配置通知服务")
                    self._notification_service = None
                    return
                
                email_config = None
                wecom_config = None
                
                # 邮件配置
                if config.email_enabled:
                    email_config = {
                        "enabled": True,
                        "smtp_host": config.email_smtp_host,
                        "smtp_port": config.email_smtp_port,
                        "username": config.email_username,
                        "password": config.email_password,
                        "to": config.email_to,
                    }
                    print(f"[通知] 邮件通知已启用 -> {config.email_to}")
                
                # 企业微信配置
                if config.wecom_enabled:
                    wecom_config = {
                        "enabled": True,
                        "webhook": config.wecom_webhook,
                    }
                    print("[通知] 企业微信通知已启用")
                
                if email_config or wecom_config:
                    self._notification_service = NotificationService(
                        email_config=email_config,
                        wecom_config=wecom_config,
                    )
                else:
                    print("[通知] 未启用任何通知服务")
                    self._notification_service = None
                    
        except Exception as e:
            print(f"[通知] 初始化失败: {e}")
            self._notification_service = None
    
    async def start(self, task_ids: Optional[List[int]] = None):
        """
        开始抢课
        
        Args:
            task_ids: 指定任务ID列表，为空则抢所有 pending 任务
        """
        if self.is_running:
            return {"success": False, "message": "抢课引擎已在运行"}
        
        self.is_running = True
        self.success_count = 0
        self.failed_count = 0
        self._success_kcdm.clear()
        
        # 从数据库加载通知配置并初始化通知服务
        await self._init_notification_service()
        
        async with AsyncSessionLocal() as db:
            tasks = await self._get_tasks_to_grab(db, task_ids)
            
            if not tasks:
                self.is_running = False
                return {"success": False, "message": "没有待抢课程"}
            
            # 更新任务状态为 grabbing
            for task in tasks:
                await self._update_task_status(task.bjdm, "grabbing")
            
            # 启动 CSRF 刷新任务
            self._csrf_refresh_task = asyncio.create_task(self._refresh_csrf_loop())
            
            # 为每个课程创建抢课任务
            for task in tasks:
                task_info = {
                    "bjmc": task.bjmc,
                    "rkjs": task.rkjs,
                    "pksj": task.pksj,
                    "pkdd": task.pkdd,
                }
                
                t = asyncio.create_task(
                    self._grab_single_course(
                        task.bjdm,
                        task.kcdm,
                        task.kcmc,
                        task_info,
                    )
                )
                self.active_tasks[task.bjdm] = t
                
                # 任务完成后自动清理
                def cleanup(future, bjdm=task.bjdm):
                    if bjdm in self.active_tasks:
                        del self.active_tasks[bjdm]
                        
                t.add_done_callback(cleanup)
        
        return {
            "success": True,
            "message": f"已开始抢课，共 {len(self.active_tasks)} 个任务",
            "task_count": len(self.active_tasks)
        }
    
    async def stop(self, task_ids: Optional[List[int]] = None):
        """
        停止抢课
        
        Args:
            task_ids: 指定任务ID列表，为空则停止所有
        """
        if not self.is_running:
            return {"success": False, "message": "抢课引擎未运行"}
        
        if task_ids:
            # 停止指定任务
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(GrabTask).where(GrabTask.id.in_(task_ids))
                )
                tasks = result.scalars().all()
                
                for task in tasks:
                    if task.bjdm in self.active_tasks:
                        self.active_tasks[task.bjdm].cancel()
                        del self.active_tasks[task.bjdm]
                        await self._update_task_status(task.bjdm, "pending")
            
            if not self.active_tasks:
                self.is_running = False
                if self._csrf_refresh_task:
                    self._csrf_refresh_task.cancel()
        else:
            # 停止所有任务
            self.is_running = False
            
            if self._csrf_refresh_task:
                self._csrf_refresh_task.cancel()
            
            for bjdm, task in list(self.active_tasks.items()):
                task.cancel()
                await self._update_task_status(bjdm, "pending")
            
            self.active_tasks.clear()
        
        return {
            "success": True,
            "message": "抢课已停止",
            "remaining_tasks": len(self.active_tasks)
        }
    
    def get_status(self) -> dict:
        """获取当前状态"""
        return {
            "is_running": self.is_running,
            "active_tasks": len(self.active_tasks),
            "success_count": self.success_count,
            "failed_count": self.failed_count,
            "current_tasks": list(self.active_tasks.keys()),
        }


# 全局引擎实例
_engine_instance: Optional[GrabberEngine] = None


def get_grabber_engine() -> GrabberEngine:
    """获取抢课引擎单例"""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = GrabberEngine()
    return _engine_instance
