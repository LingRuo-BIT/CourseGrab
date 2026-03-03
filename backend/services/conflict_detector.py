# -*- coding: utf-8 -*-
"""
冲突检测服务
检测课程时间冲突（已选课程 + 抢课队列）
"""

import json
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import GrabTask, SelectedCourse
from utils.time_parser import (
    parse_pksj,
    check_courses_conflict,
    format_conflict_description,
    TimeSlot,
)
from models import ConflictDetail


class ConflictDetector:
    """冲突检测器"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_selected_courses(self) -> List[Dict[str, Any]]:
        """获取已选课程列表"""
        result = await self.db.execute(select(SelectedCourse))
        courses = result.scalars().all()
        
        course_list = []
        for c in courses:
            course_data = json.loads(c.course_data) if c.course_data else {}
            course_dict = {
                "bjdm": c.bjdm,
                "kcdm": c.kcdm,
                "pksj": course_data.get("PKSJ", ""),
                "kcmc": course_data.get("KCMC", ""),
            }
            course_dict.update(course_data)
            course_list.append(course_dict)
        
        return course_list

    
    async def get_queue_courses(self, exclude_bjdm: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取队列中的课程列表（排除指定课程）"""
        query = select(GrabTask).where(
            GrabTask.status.in_(["pending", "grabbing"])
        )
        if exclude_bjdm:
            query = query.where(GrabTask.bjdm != exclude_bjdm)
        
        result = await self.db.execute(query)
        tasks = result.scalars().all()
        
        return [
            {
                "bjdm": t.bjdm,
                "kcdm": t.kcdm,
                "kcmc": t.kcmc,
                "pksj": t.pksj or "",
            }
            for t in tasks
        ]
    
    def _create_conflict_detail(
        self,
        course1: Dict[str, Any],
        course2: Dict[str, Any],
        conflict: Dict
    ) -> ConflictDetail:
        """创建冲突详情对象"""
        return ConflictDetail(
            course1_bjdm=course1.get("bjdm", ""),
            course1_kcmc=course1.get("kcmc", ""),
            course2_bjdm=course2.get("bjdm", ""),
            course2_kcmc=course2.get("kcmc", ""),
            conflict_weeks=conflict["conflict_weeks"],
            conflict_weekday=conflict["conflict_weekday"],
            conflict_sections=conflict["conflict_sections"],
            description=format_conflict_description(conflict),
        )
    
    async def check_conflict_with_selected(
        self,
        bjdm: str,
        pksj: str,
        kcmc: str = ""
    ) -> List[ConflictDetail]:
        """检查与已选课程的冲突"""
        selected = await self.get_selected_courses()
        
        conflicts = []
        target_course = {"bjdm": bjdm, "kcmc": kcmc, "pksj": pksj}
        
        for course in selected:
            if course["bjdm"] == bjdm:
                continue  # 跳过自己
            
            course_pksj = course.get("pksj", "")
            if not course_pksj:
                continue
            
            conflict_list = check_courses_conflict(pksj, course_pksj)
            for conflict in conflict_list:
                conflicts.append(
                    self._create_conflict_detail(target_course, course, conflict)
                )
        
        return conflicts
    
    async def check_conflict_with_queue(
        self,
        bjdm: str,
        pksj: str,
        kcmc: str = ""
    ) -> List[ConflictDetail]:
        """检查与队列中课程的冲突"""
        queue_courses = await self.get_queue_courses(exclude_bjdm=bjdm)
        
        conflicts = []
        target_course = {"bjdm": bjdm, "kcmc": kcmc, "pksj": pksj}
        
        for course in queue_courses:
            course_pksj = course.get("pksj", "")
            if not course_pksj:
                continue
            
            conflict_list = check_courses_conflict(pksj, course_pksj)
            for conflict in conflict_list:
                conflicts.append(
                    self._create_conflict_detail(target_course, course, conflict)
                )
        
        return conflicts
    
    async def check_all_conflicts(
        self,
        bjdm: str,
        pksj: str,
        kcmc: str = ""
    ) -> Dict[str, List[ConflictDetail]]:
        """
        检查所有冲突（已选课程 + 队列课程）
        
        Returns:
            {
                "with_selected": [...],
                "with_queue": [...],
                "has_conflict": bool
            }
        """
        conflicts_with_selected = await self.check_conflict_with_selected(bjdm, pksj, kcmc)
        conflicts_with_queue = await self.check_conflict_with_queue(bjdm, pksj, kcmc)
        
        return {
            "with_selected": conflicts_with_selected,
            "with_queue": conflicts_with_queue,
            "has_conflict": bool(conflicts_with_selected or conflicts_with_queue)
        }
    
    async def get_queue_internal_conflicts(self) -> List[Dict[str, Any]]:
        """
        获取队列内部的所有冲突
        用于在课表中标注冲突
        """
        queue_courses = await self.get_queue_courses()
        all_conflicts = []
        
        for i, course1 in enumerate(queue_courses):
            for course2 in queue_courses[i+1:]:
                # 同一门课程（相同 kcdm）不检测冲突
                if course1.get("kcdm") == course2.get("kcdm"):
                    continue
                
                pksj1 = course1.get("pksj", "")
                pksj2 = course2.get("pksj", "")
                
                if not pksj1 or not pksj2:
                    continue
                
                conflict_list = check_courses_conflict(pksj1, pksj2)
                for conflict in conflict_list:
                    all_conflicts.append({
                        "course1": course1,
                        "course2": course2,
                        "conflict": conflict,
                        "description": format_conflict_description(conflict)
                    })
        
        return all_conflicts


async def get_conflict_detector(db: AsyncSession) -> ConflictDetector:
    """获取冲突检测器实例"""
    return ConflictDetector(db)
