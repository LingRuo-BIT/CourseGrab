# -*- coding: utf-8 -*-
"""
抢课队列路由
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List, Optional

from database import get_db, GrabTask
from models import (
    GrabTaskCreate,
    GrabTaskResponse,
    GrabTaskBatchAdd,
    ApiResponse,
)
from services.conflict_detector import ConflictDetector

router = APIRouter(prefix="/queue", tags=["抢课队列"])


@router.get("", response_model=ApiResponse)
async def get_queue(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    获取抢课队列列表
    
    Args:
        status: 可选，按状态筛选 (pending/grabbing/success/failed/cancelled)
    """
    query = select(GrabTask).order_by(GrabTask.priority.desc(), GrabTask.created_at)
    if status:
        query = query.where(GrabTask.status == status)
    
    result = await db.execute(query)
    tasks = result.scalars().all()
    
    # 检测队列内冲突
    detector = ConflictDetector(db)
    conflicts = await detector.get_queue_internal_conflicts()
    
    # 构建冲突映射
    conflict_map = {}
    for c in conflicts:
        bjdm1 = c["course1"]["bjdm"]
        bjdm2 = c["course2"]["bjdm"]
        if bjdm1 not in conflict_map:
            conflict_map[bjdm1] = []
        if bjdm2 not in conflict_map:
            conflict_map[bjdm2] = []
        conflict_map[bjdm1].append(bjdm2)
        conflict_map[bjdm2].append(bjdm1)
    
    # 构建响应数据
    data = []
    for task in tasks:
        task_dict = {
            "id": task.id,
            "bjdm": task.bjdm,
            "kcdm": task.kcdm,
            "kcmc": task.kcmc,
            "bjmc": task.bjmc,
            "rkjs": task.rkjs,
            "pksj": task.pksj,
            "pkdd": task.pkdd,
            "xnxqmc": task.xnxqmc,
            "kxrs": task.kxrs,
            "dqrs": task.dqrs,
            "priority": task.priority,
            "status": task.status,
            "error_msg": task.error_msg,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "updated_at": task.updated_at.isoformat() if task.updated_at else None,
            "is_queue_conflict": task.bjdm in conflict_map,
            "conflict_with": conflict_map.get(task.bjdm, []),
        }
        data.append(task_dict)
    
    return ApiResponse(
        success=True,
        message=f"共 {len(data)} 个任务",
        data=data,
    )


@router.post("", response_model=ApiResponse)
async def add_to_queue(
    task: GrabTaskCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    添加课程到抢课队列
    """
    # 检查是否已存在
    result = await db.execute(
        select(GrabTask).where(GrabTask.bjdm == task.bjdm)
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        return ApiResponse(
            success=False,
            message="该课程已在队列中",
            data={"bjdm": task.bjdm}
        )
    
    # 检测冲突
    detector = ConflictDetector(db)
    conflicts = await detector.check_all_conflicts(
        bjdm=task.bjdm,
        pksj=task.pksj or "",
        kcmc=task.kcmc,
    )
    
    # 添加到数据库
    new_task = GrabTask(
        bjdm=task.bjdm,
        kcdm=task.kcdm,
        kcmc=task.kcmc,
        bjmc=task.bjmc,
        rkjs=task.rkjs,
        pksj=task.pksj,
        pkdd=task.pkdd,
        xnxqmc=task.xnxqmc,
        kxrs=task.kxrs,
        dqrs=task.dqrs,
        priority=task.priority,
        status="pending",
    )
    db.add(new_task)
    await db.commit()
    await db.refresh(new_task)
    
    return ApiResponse(
        success=True,
        message="添加成功" + ("（存在冲突）" if conflicts["has_conflict"] else ""),
        data={
            "id": new_task.id,
            "bjdm": new_task.bjdm,
            "has_conflict": conflicts["has_conflict"],
            "conflicts_with_selected": len(conflicts["with_selected"]),
            "conflicts_with_queue": len(conflicts["with_queue"]),
        }
    )


@router.post("/batch", response_model=ApiResponse)
async def batch_add_to_queue(
    request: GrabTaskBatchAdd,
    db: AsyncSession = Depends(get_db),
):
    """
    批量添加课程到抢课队列
    """
    added = []
    skipped = []
    
    for task in request.tasks:
        # 检查是否已存在
        result = await db.execute(
            select(GrabTask).where(GrabTask.bjdm == task.bjdm)
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            skipped.append(task.bjdm)
            continue
        
        new_task = GrabTask(
            bjdm=task.bjdm,
            kcdm=task.kcdm,
            kcmc=task.kcmc,
            bjmc=task.bjmc,
            rkjs=task.rkjs,
            pksj=task.pksj,
            pkdd=task.pkdd,
            xnxqmc=task.xnxqmc,
            kxrs=task.kxrs,
            dqrs=task.dqrs,
            priority=task.priority,
            status="pending",
        )
        db.add(new_task)
        added.append(task.bjdm)
    
    await db.commit()
    
    return ApiResponse(
        success=True,
        message=f"添加 {len(added)} 个，跳过 {len(skipped)} 个已存在的",
        data={
            "added": added,
            "skipped": skipped,
        }
    )


@router.delete("/{bjdm}", response_model=ApiResponse)
async def remove_from_queue(
    bjdm: str,
    db: AsyncSession = Depends(get_db),
):
    """
    从队列中移除课程
    """
    result = await db.execute(
        select(GrabTask).where(GrabTask.bjdm == bjdm)
    )
    task = result.scalar_one_or_none()
    
    if not task:
        return ApiResponse(
            success=False,
            message="任务不存在",
        )
    
    if task.status == "grabbing":
        return ApiResponse(
            success=False,
            message="任务正在抢课中，请先停止抢课",
        )
    
    await db.execute(
        delete(GrabTask).where(GrabTask.bjdm == bjdm)
    )
    await db.commit()
    
    return ApiResponse(
        success=True,
        message="移除成功",
    )


@router.delete("", response_model=ApiResponse)
async def clear_queue(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    清空队列
    
    Args:
        status: 可选，只清除指定状态的任务
    """
    query = delete(GrabTask)
    if status:
        query = query.where(GrabTask.status == status)
    else:
        # 不删除正在抢课的
        query = query.where(GrabTask.status != "grabbing")
    
    result = await db.execute(query)
    await db.commit()
    
    return ApiResponse(
        success=True,
        message=f"已清除 {result.rowcount} 个任务",
    )


@router.put("/{bjdm}/priority", response_model=ApiResponse)
async def update_priority(
    bjdm: str,
    priority: int,
    db: AsyncSession = Depends(get_db),
):
    """
    更新任务优先级
    """
    result = await db.execute(
        select(GrabTask).where(GrabTask.bjdm == bjdm)
    )
    task = result.scalar_one_or_none()
    
    if not task:
        return ApiResponse(
            success=False,
            message="任务不存在",
        )
    
    task.priority = priority
    await db.commit()
    
    return ApiResponse(
        success=True,
        message="优先级更新成功",
    )
