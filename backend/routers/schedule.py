# -*- coding: utf-8 -*-
"""
课表路由
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from database import get_db
from models import ApiResponse
from services.schedule_builder import ScheduleBuilder

router = APIRouter(prefix="/schedule", tags=["课表"])


@router.get("", response_model=ApiResponse)
async def get_schedule(
    semester: Optional[str] = Query(None, description="指定学期"),
    include_queue: bool = Query(True, description="是否包含队列中的课程"),
    db: AsyncSession = Depends(get_db),
):
    """
    获取课表数据
    """
    builder = ScheduleBuilder(db)
    schedule = await builder.build_schedule(
        semester=semester,
        include_queue=include_queue,
    )
    
    return ApiResponse(
        success=True,
        message="获取成功",
        data=schedule,
    )


@router.get("/semesters", response_model=ApiResponse)
async def get_semesters(
    db: AsyncSession = Depends(get_db),
):
    """
    获取所有学期列表
    """
    builder = ScheduleBuilder(db)
    selected = await builder.get_selected_courses_by_semester()
    queue = await builder.get_queue_courses_by_semester()
    
    all_semesters = sorted(set(selected.keys()) | set(queue.keys()))
    
    return ApiResponse(
        success=True,
        message=f"共 {len(all_semesters)} 个学期",
        data=all_semesters,
    )
