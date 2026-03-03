# -*- coding: utf-8 -*-
"""
课程相关路由
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
import json

from database import get_db, SelectedCourse
from models import (
    CourseSearchRequest,
    CourseSearchResponse,
    CourseInfo,
    ApiResponse,
    ConflictCheckRequest,
    ConflictCheckResponse,
)
from services.api_client import BitApiClient
from services.conflict_detector import ConflictDetector

router = APIRouter(prefix="/courses", tags=["课程"])


@router.get("/departments", response_model=ApiResponse)
async def get_departments(
    db: AsyncSession = Depends(get_db),
):
    """
    获取开课院系列表
    """
    client = BitApiClient(db)
    departments = await client.get_departments()
    
    return ApiResponse(
        success=True,
        message=f"获取成功，共 {len(departments)} 个院系",
        data=departments,
    )


@router.get("/search", response_model=ApiResponse)
async def search_courses(
    keyword: str = Query(..., description="搜索关键词"),
    college: str = Query("", description="开课院系代码"),
    page_index: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=50, description="每页数量"),
    db: AsyncSession = Depends(get_db),
):
    """
    搜索课程
    """
    client = BitApiClient(db)
    result = await client.search_courses(
        keyword=keyword,
        college=college,
        page_index=page_index,
        page_size=page_size,
    )
    
    # 获取队列课程用于冲突检测
    conflict_detector = ConflictDetector(db)
    queue_courses = await conflict_detector.get_queue_courses()
    queue_pksj_map = {c["bjdm"]: c.get("pksj", "") for c in queue_courses}
    
    # 处理返回数据，添加队列冲突标记
    courses = result.get("datas", [])
    for course in courses:
        # 检查与队列课程的冲突
        pksj = course.get("PKSJ", "")
        bjdm = course.get("BJDM", "")
        
        # 检查是否与队列中的课程冲突
        queue_conflict = False
        if pksj:
            for q_bjdm, q_pksj in queue_pksj_map.items():
                if q_bjdm != bjdm and q_pksj:
                    from utils.time_parser import check_courses_conflict
                    if check_courses_conflict(pksj, q_pksj):
                        queue_conflict = True
                        break
        
        course["IS_QUEUE_CONFLICT"] = 1 if queue_conflict else 0
    
    return ApiResponse(
        success=True,
        message="搜索成功",
        data={
            "courses": courses,
            "total": result.get("total", 0),
            "pageIndex": result.get("pageIndex", page_index),
            "pageSize": result.get("pageSize", page_size),
        }
    )


@router.get("/selected", response_model=ApiResponse)
async def get_selected_courses(
    db: AsyncSession = Depends(get_db),
):
    """
    获取已选课程列表（从服务器同步）
    """
    client = BitApiClient(db)
    courses = await client.get_selected_courses()
    
    # 清空本地已选课程表，防止旧账号数据残留
    await db.execute(delete(SelectedCourse))
    
    # 对课程按 BJDM 去重（API可能返回重复数据）
    seen_bjdm = set()
    unique_courses = []
    for course in courses:
        bjdm = course.get("BJDM", "")
        if bjdm and bjdm not in seen_bjdm:
            seen_bjdm.add(bjdm)
            unique_courses.append(course)
    
    # 同步到本地数据库
    for course in unique_courses:
        bjdm = course.get("BJDM", "")
        if not bjdm:
            continue
        
        # 直接插入新记录
        new_course = SelectedCourse(
            bjdm=bjdm,
            kcdm=course.get("KCDM", ""),
            course_data=json.dumps(course),
            xnxqmc=course.get("XNXQMC", ""),
        )
        db.add(new_course)
    
    await db.commit()
    
    return ApiResponse(
        success=True,
        message=f"获取成功，共 {len(unique_courses)} 门课程",
        data=unique_courses,
    )


@router.get("/selected/local", response_model=ApiResponse)
async def get_local_selected_courses(
    db: AsyncSession = Depends(get_db),
):
    """
    获取本地缓存的已选课程
    """
    result = await db.execute(select(SelectedCourse))
    courses = result.scalars().all()
    
    data = []
    for c in courses:
        course_data = json.loads(c.course_data) if c.course_data else {}
        course_data["_synced_at"] = c.synced_at.isoformat() if c.synced_at else None
        data.append(course_data)
    
    return ApiResponse(
        success=True,
        message=f"共 {len(data)} 门课程",
        data=data,
    )


@router.post("/conflict/check", response_model=ApiResponse)
async def check_conflict(
    request: ConflictCheckRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    检查课程冲突
    """
    detector = ConflictDetector(db)
    result = await detector.check_all_conflicts(
        bjdm=request.bjdm,
        pksj=request.pksj,
    )
    
    return ApiResponse(
        success=True,
        message="冲突检测完成",
        data={
            "has_conflict": result["has_conflict"],
            "with_selected": [c.model_dump() for c in result["with_selected"]],
            "with_queue": [c.model_dump() for c in result["with_queue"]],
        }
    )


@router.post("/cancel", response_model=ApiResponse)
async def cancel_course(
    bjdm: str,
    db: AsyncSession = Depends(get_db),
):
    """
    退课
    """
    client = BitApiClient(db)
    result = await client.cancel_course(bjdm)
    
    if result.get("code") == 1:
        # 退课成功，从本地已选课程表删除
        await db.execute(
            delete(SelectedCourse).where(SelectedCourse.bjdm == bjdm)
        )
        await db.commit()
        
        return ApiResponse(
            success=True,
            message="退课成功",
        )
    else:
        return ApiResponse(
            success=False,
            message=result.get("msg", "退课失败"),
            data={"token_expired": result.get("token_expired", False)}
        )


@router.get("/list", response_model=ApiResponse)
async def get_course_list(
    db: AsyncSession = Depends(get_db),
):
    """
    获取课程列表（含完整状态信息）
    用于课表页面的课程列表展示
    """
    client = BitApiClient(db)
    courses = await client.get_selected_courses()
    
    # 先找出所有正式选中的课程 bjdm（SFYXXKJG=0）
    confirmed_bjdm = {
        c.get("BJDM") for c in courses 
        if c.get("SFYXXKJG") == 0
    }
    
    # 处理课程状态
    course_list = []
    for c in courses:
        bjdm = c.get("BJDM")
        sfyxxkjg = c.get("SFYXXKJG")
        sfxz = c.get("SFXZ")
        
        if sfyxxkjg == 0:
            status = "confirmed"  # 正式选中
            status_text = "正式选中"
        elif sfyxxkjg == 1:
            if sfxz == 1:
                # 抽中状态：如果存在相同bjdm的正式记录，则忽略此条
                if bjdm in confirmed_bjdm:
                    continue
                status = "won"  # 抽中（待入库）
                status_text = "已中签"
            elif sfxz is None:
                status = "pending"  # 待抽签
                status_text = "待抽签"
            elif sfxz == 0:
                status = "failed"  # 未中签
                status_text = "未中签"
            else:
                status = "unknown"
                status_text = f"状态异常 (SFXZ={sfxz})"
        else:
            status = "unknown"
            status_text = f"状态异常 (SFYXXKJG={sfyxxkjg})"
        
        course_list.append({
            "bjdm": bjdm,
            "kcdm": c.get("KCDM"),
            "kcmc": c.get("KCMC"),
            "bjmc": c.get("BJMC"),
            "rkjs": c.get("RKJS"),
            "xf": c.get("XF"),
            "pksj": c.get("PKSJDD") or c.get("PKSJ", ""),
            "xnxqmc": c.get("XNXQMC"),
            "kckkdwmc": c.get("KCKKDWMC"),
            "status": status,
            "status_text": status_text,
            "can_cancel": c.get("IS_SFYXTK") == 1,  # 是否允许退课
        })
    
    return ApiResponse(
        success=True,
        message=f"共 {len(course_list)} 门课程",
        data=course_list,
    )

