# -*- coding: utf-8 -*-
"""
课表构建服务
根据已选课程和队列课程生成课表数据
"""

import json
from typing import List, Dict, Any, Optional
from collections import defaultdict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import SelectedCourse, GrabTask
from utils.time_parser import parse_pksj, TimeSlot
from models import ScheduleCourse, ScheduleResponse
from services.conflict_detector import ConflictDetector


class ScheduleBuilder:
    """课表构建器"""
    
    # 节次对应的时间
    SECTION_TIMES = {
        1: "08:00-08:45",
        2: "08:50-09:35",
        3: "09:55-10:40",
        4: "10:45-11:30",
        5: "11:35-12:20",
        6: "13:20-14:05",
        7: "14:10-14:55",
        8: "15:15-16:00",
        9: "16:05-16:50",
        10: "16:55-17:40",
        11: "18:30-19:15",
        12: "19:20-20:05",
        13: "20:10-20:55",
    }
    
    # 大节分组：(名称, 时间范围, 包含的小节)
    BIG_SECTIONS = [
        {"id": 1, "name": "第1-2节", "time": "08:00-09:35", "sections": [1, 2]},
        {"id": 2, "name": "第3-5节", "time": "09:55-12:20", "sections": [3, 4, 5]},
        {"id": 3, "name": "第6-7节", "time": "13:20-14:55", "sections": [6, 7]},
        {"id": 4, "name": "第8-10节", "time": "15:15-17:40", "sections": [8, 9, 10]},
        {"id": 5, "name": "第11-13节", "time": "18:30-20:55", "sections": [11, 12, 13]},
    ]
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.conflict_detector = ConflictDetector(db)
    
    async def get_selected_courses_by_semester(self) -> Dict[str, List[Dict]]:
        """
        获取已选课程，按学期分组
        
        Returns:
            {"2025-2026学年 第一学期": [...], "2025-2026学年 第二学期": [...]}
        """
        result = await self.db.execute(select(SelectedCourse))
        courses = result.scalars().all()
        
        courses_by_semester = defaultdict(list)
        
        for c in courses:
            data = json.loads(c.course_data) if c.course_data else {}
            semester = c.xnxqmc or data.get("XNXQMC", "未知学期")
            
            # PKSJ 可能为空，优先使用 PKSJDD 或 PKSJDDMS
            pksj = data.get("PKSJ", "") or data.get("PKSJDD", "") or data.get("PKSJDDMS", "")
            # 清理 HTML 标签（如 <br/>）
            pksj = pksj.replace("<br/>", ";").replace("<br>", ";")
            
            pkdd = data.get("PKDD", "") or data.get("XQMC", "")
            
            courses_by_semester[semester].append({
                "bjdm": c.bjdm,
                "kcdm": c.kcdm,
                "kcmc": data.get("KCMC", ""),
                "bjmc": data.get("BJMC", ""),
                "rkjs": data.get("RKJS", ""),
                "pksj": pksj,
                "pkdd": pkdd,
                "source": "selected",  # 来源：已选
            })
        
        return dict(courses_by_semester)
    
    async def get_queue_courses_by_semester(self) -> Dict[str, List[Dict]]:
        """
        获取队列课程，按学期分组
        """
        result = await self.db.execute(
            select(GrabTask).where(
                GrabTask.status.in_(["pending", "grabbing"])
            )
        )
        tasks = result.scalars().all()
        
        courses_by_semester = defaultdict(list)
        
        for t in tasks:
            semester = t.xnxqmc or "未知学期"
            
            courses_by_semester[semester].append({
                "bjdm": t.bjdm,
                "kcdm": t.kcdm,
                "kcmc": t.kcmc,
                "bjmc": t.bjmc or "",
                "rkjs": t.rkjs or "",
                "pksj": t.pksj or "",
                "pkdd": t.pkdd or "",
                "source": "queue",  # 来源：队列
                "status": t.status,
            })
        
        return dict(courses_by_semester)
    
    def _build_schedule_grid(
        self,
        courses: List[Dict],
        include_queue: bool = True
    ) -> Dict[str, Any]:
        """
        构建课表网格数据
        
        Returns:
            {
                "grid": {
                    1: {  # 周一
                        1: [...],  # 第1节的课程列表
                        2: [...],
                        ...
                    },
                    ...
                },
                "courses": [...],  # 处理后的课程列表
                "conflicts": [...]  # 冲突信息
            }
        """
        # 初始化网格: weekday -> section -> courses
        grid = {
            weekday: {section: [] for section in range(1, 14)}
            for weekday in range(1, 8)
        }
        
        processed_courses = []
        
        # 用于合并同一课程在同一节次的周次
        # key: (weekday, section, bjdm) -> course_dict with accumulated weeks
        cell_course_map = {}
        
        for course in courses:
            pksj = course.get("pksj", "")
            if not pksj:
                continue
            
            time_slots = parse_pksj(pksj)
            
            course_info = {
                "bjdm": course.get("bjdm", ""),
                "kcdm": course.get("kcdm", ""),
                "kcmc": course.get("kcmc", ""),
                "bjmc": course.get("bjmc", ""),
                "rkjs": course.get("rkjs", ""),
                "pkdd": course.get("pkdd", ""),
                "source": course.get("source", "selected"),
                "time_slots": [
                    {
                        "weeks": slot.weeks,
                        "weekday": slot.weekday,
                        "sections": slot.sections,
                    }
                    for slot in time_slots
                ],
            }
            
            processed_courses.append(course_info)
            
            # 填充网格（使用map进行合并）
            for slot in time_slots:
                for section in slot.sections:
                    key = (slot.weekday, section, course.get("bjdm", ""))
                    
                    if key in cell_course_map:
                        # 合并周次
                        existing_weeks = set(cell_course_map[key]["weeks"])
                        existing_weeks.update(slot.weeks)
                        cell_course_map[key]["weeks"] = sorted(existing_weeks)
                    else:
                        # 新增
                        cell_course_map[key] = {
                            "bjdm": course.get("bjdm", ""),
                            "kcmc": course.get("kcmc", ""),
                            "pkdd": course.get("pkdd", ""),
                            "rkjs": course.get("rkjs", ""),
                            "weeks": sorted(slot.weeks),
                            "source": course.get("source", "selected"),
                            "has_conflict": False,
                        }
        
        # 将合并后的课程填入网格
        for (weekday, section, bjdm), course_data in cell_course_map.items():
            grid[weekday][section].append(course_data)
        
        # 检测冲突并标记
        conflicts = []
        conflict_bjdms = set()  # 记录有冲突的课程bjdm
        
        for weekday in range(1, 8):
            for section in range(1, 14):
                cell_courses = grid[weekday][section]
                if len(cell_courses) > 1:
                    # 有多门课，检查周次是否有重叠
                    for i, c1 in enumerate(cell_courses):
                        for c2 in cell_courses[i+1:]:
                            weeks_overlap = set(c1["weeks"]) & set(c2["weeks"])
                            if weeks_overlap:
                                # 标记两门课都有冲突
                                c1["has_conflict"] = True
                                c2["has_conflict"] = True
                                conflict_bjdms.add(c1["bjdm"])
                                conflict_bjdms.add(c2["bjdm"])
                                
                                conflicts.append({
                                    "weekday": weekday,
                                    "section": section,
                                    "weeks": sorted(list(weeks_overlap)),
                                    "courses": [c1["kcmc"], c2["kcmc"]],
                                })
        
        # 构建按大节分组的网格
        big_grid = {
            weekday: {big_sec["id"]: [] for big_sec in self.BIG_SECTIONS}
            for weekday in range(1, 8)
        }
        
        # 合并大节内的课程（去重）
        for weekday in range(1, 8):
            for big_sec in self.BIG_SECTIONS:
                big_sec_id = big_sec["id"]
                seen_bjdms = {}  # 用于合并同一课程在大节内的显示
                
                for section in big_sec["sections"]:
                    for course in grid[weekday][section]:
                        bjdm = course["bjdm"]
                        if bjdm in seen_bjdms:
                            # 合并周次
                            existing_weeks = set(seen_bjdms[bjdm]["weeks"])
                            existing_weeks.update(course["weeks"])
                            seen_bjdms[bjdm]["weeks"] = sorted(existing_weeks)
                            # 如果任一有冲突，标记冲突
                            if course.get("has_conflict"):
                                seen_bjdms[bjdm]["has_conflict"] = True
                        else:
                            seen_bjdms[bjdm] = {**course}
                
                big_grid[weekday][big_sec_id] = list(seen_bjdms.values())
        
        return {
            "grid": grid,  # 原始小节网格（兼容）
            "big_grid": big_grid,  # 大节网格
            "big_sections": self.BIG_SECTIONS,  # 大节配置
            "courses": processed_courses,
            "conflicts": conflicts,
            "conflict_bjdms": list(conflict_bjdms),
        }
    
    async def build_schedule(
        self,
        semester: Optional[str] = None,
        include_queue: bool = True,
    ) -> Dict[str, Any]:
        """
        构建课表
        
        Args:
            semester: 指定学期，为空则返回所有学期
            include_queue: 是否包含队列中的课程
        
        Returns:
            {
                "semesters": ["2025-2026学年 第一学期", ...],
                "current_semester": "...",
                "schedules": {
                    "2025-2026学年 第一学期": { grid, courses, conflicts },
                    ...
                }
            }
        """
        selected_by_semester = await self.get_selected_courses_by_semester()
        queue_by_semester = await self.get_queue_courses_by_semester() if include_queue else {}
        
        # 合并学期列表
        all_semesters = sorted(set(selected_by_semester.keys()) | set(queue_by_semester.keys()))
        
        schedules = {}
        
        for sem in all_semesters:
            if semester and sem != semester:
                continue
            
            courses = selected_by_semester.get(sem, [])
            if include_queue:
                courses.extend(queue_by_semester.get(sem, []))
            
            schedules[sem] = self._build_schedule_grid(courses, include_queue)
        
        # 确定当前学期（包含"第二学期"的优先）
        current_semester = None
        for sem in all_semesters:
            if "第二学期" in sem:
                current_semester = sem
                break
        if not current_semester and all_semesters:
            current_semester = all_semesters[-1]
        
        return {
            "semesters": all_semesters,
            "current_semester": current_semester,
            "schedules": schedules,
            "section_times": self.SECTION_TIMES,
        }
    
    def get_section_time(self, section: int) -> str:
        """获取节次对应的时间"""
        return self.SECTION_TIMES.get(section, "")


async def get_schedule_builder(db: AsyncSession) -> ScheduleBuilder:
    """获取课表构建器实例"""
    return ScheduleBuilder(db)
