# -*- coding: utf-8 -*-
"""
时间解析工具
用于解析课程时间字符串，如 "7-9周 星期二[3-5节]"
"""

import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class TimeSlot:
    """时间段"""
    weeks: List[int]
    weekday: int  # 1-7 代表周一到周日
    sections: List[int]  # 节次列表


# 星期映射
WEEKDAY_MAP = {
    "一": 1, "二": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "日": 7, "天": 7
}


def parse_weeks(week_str: str) -> List[int]:
    """
    解析周次字符串
    
    支持格式:
    - "7-9周" -> [7, 8, 9]
    - "1-16周(单)" -> [1, 3, 5, ..., 15]
    - "1-16周(双)" -> [2, 4, 6, ..., 16]
    - "1-8,10-16周" -> [1, 2, ..., 8, 10, 11, ..., 16]
    - "8,10-15周" -> [8, 10, 11, ..., 15]
    """
    weeks = []
    
    # 检查是否为单/双周
    is_odd = "(单)" in week_str or "（单）" in week_str
    is_even = "(双)" in week_str or "（双）" in week_str
    
    # 移除"周"字和单双周标识
    week_str = re.sub(r'[周(单)(双)（单）（双）]', '', week_str)
    
    # 分割多个范围（用逗号分隔）
    ranges = week_str.split(',')
    
    for r in ranges:
        r = r.strip()
        if not r:
            continue
            
        if '-' in r:
            # 范围格式: "7-9"
            parts = r.split('-')
            if len(parts) == 2:
                try:
                    start = int(parts[0].strip())
                    end = int(parts[1].strip())
                    weeks.extend(range(start, end + 1))
                except ValueError:
                    pass
        else:
            # 单个周次
            try:
                weeks.append(int(r))
            except ValueError:
                pass
    
    # 过滤单双周
    if is_odd:
        weeks = [w for w in weeks if w % 2 == 1]
    elif is_even:
        weeks = [w for w in weeks if w % 2 == 0]
    
    return sorted(list(set(weeks)))


def parse_sections(section_str: str) -> List[int]:
    """
    解析节次字符串
    
    支持格式:
    - "[3-5节]" -> [3, 4, 5]
    - "[1-2节]" -> [1, 2]
    - "[9-10节]" -> [9, 10]
    """
    sections = []
    
    # 提取方括号内的内容
    match = re.search(r'\[([^\]]+)\]', section_str)
    if not match:
        # 尝试不带方括号的格式
        match = re.search(r'(\d+[-,\d]*节)', section_str)
        if match:
            section_str = match.group(1)
        else:
            return sections
    else:
        section_str = match.group(1)
    
    # 移除"节"字
    section_str = section_str.replace('节', '')
    
    # 分割多个范围
    ranges = section_str.split(',')
    
    for r in ranges:
        r = r.strip()
        if not r:
            continue
            
        if '-' in r:
            parts = r.split('-')
            if len(parts) == 2:
                try:
                    start = int(parts[0].strip())
                    end = int(parts[1].strip())
                    sections.extend(range(start, end + 1))
                except ValueError:
                    pass
        else:
            try:
                sections.append(int(r))
            except ValueError:
                pass
    
    return sorted(list(set(sections)))


def parse_weekday(weekday_str: str) -> Optional[int]:
    """
    解析星期字符串
    
    支持格式:
    - "星期一" -> 1
    - "星期二" -> 2
    - "周一" -> 1
    """
    for key, value in WEEKDAY_MAP.items():
        if key in weekday_str:
            return value
    return None


def parse_single_time_slot(time_str: str) -> Optional[TimeSlot]:
    """
    解析单个时间段字符串
    
    示例: "7-9周 星期二[3-5节]"
    """
    # 分离周次和星期节次部分
    # 格式: "周次部分 星期X[节次]"
    
    # 提取周次部分（在"星期"或"周"之前）
    week_match = re.match(r'^([^星周]*周[^星]*)', time_str)
    if not week_match:
        # 尝试另一种格式
        week_match = re.match(r'^([\d,\-]+周(?:\([单双]\))?)', time_str)
    
    if not week_match:
        return None
    
    week_part = week_match.group(1).strip()
    rest_part = time_str[len(week_part):].strip()
    
    # 解析周次
    weeks = parse_weeks(week_part)
    if not weeks:
        return None
    
    # 解析星期
    weekday = parse_weekday(rest_part)
    if not weekday:
        return None
    
    # 解析节次
    sections = parse_sections(rest_part)
    if not sections:
        return None
    
    return TimeSlot(weeks=weeks, weekday=weekday, sections=sections)


def parse_pksj(pksj: str) -> List[TimeSlot]:
    """
    解析完整的排课时间字符串
    
    支持多个时间段，用分号分隔:
    "8-16周 星期三[9-10节];8,10-15周 星期五[9-10节]"
    
    返回 TimeSlot 列表
    """
    if not pksj:
        return []
    
    time_slots = []
    
    # 用分号分隔多个时间段
    parts = pksj.split(';')
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
        
        slot = parse_single_time_slot(part)
        if slot:
            time_slots.append(slot)
    
    return time_slots


def check_time_conflict(slot1: TimeSlot, slot2: TimeSlot) -> Optional[Dict]:
    """
    检查两个时间段是否冲突
    
    返回冲突详情，如果不冲突返回 None
    """
    # 检查星期是否相同
    if slot1.weekday != slot2.weekday:
        return None
    
    # 检查节次是否有交集
    sections_overlap = set(slot1.sections) & set(slot2.sections)
    if not sections_overlap:
        return None
    
    # 检查周次是否有交集
    weeks_overlap = set(slot1.weeks) & set(slot2.weeks)
    if not weeks_overlap:
        return None
    
    # 存在冲突
    return {
        "conflict_weeks": sorted(list(weeks_overlap)),
        "conflict_weekday": slot1.weekday,
        "conflict_sections": sorted(list(sections_overlap)),
    }


def check_courses_conflict(pksj1: str, pksj2: str) -> List[Dict]:
    """
    检查两门课程是否冲突
    
    返回所有冲突详情列表
    """
    slots1 = parse_pksj(pksj1)
    slots2 = parse_pksj(pksj2)
    
    conflicts = []
    
    for s1 in slots1:
        for s2 in slots2:
            conflict = check_time_conflict(s1, s2)
            if conflict:
                conflicts.append(conflict)
    
    return conflicts


def format_conflict_description(conflict: Dict) -> str:
    """
    格式化冲突描述
    """
    weekday_names = ["", "周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    
    weeks = conflict["conflict_weeks"]
    if len(weeks) == 1:
        week_str = f"第{weeks[0]}周"
    elif weeks == list(range(weeks[0], weeks[-1] + 1)):
        week_str = f"第{weeks[0]}-{weeks[-1]}周"
    else:
        week_str = f"第{','.join(map(str, weeks))}周"
    
    sections = conflict["conflict_sections"]
    if len(sections) == 1:
        section_str = f"第{sections[0]}节"
    else:
        section_str = f"第{sections[0]}-{sections[-1]}节"
    
    weekday_str = weekday_names[conflict["conflict_weekday"]]
    
    return f"{week_str} {weekday_str} {section_str}"


# 测试代码
if __name__ == "__main__":
    # 测试用例
    test_cases = [
        "7-9周 星期二[3-5节]",
        "1-16周(单) 星期一[1-2节]",
        "8-16周 星期三[9-10节];8,10-15周 星期五[9-10节]",
        "1-8,10-16周 星期三[6-7节]",
    ]
    
    for tc in test_cases:
        print(f"\n输入: {tc}")
        slots = parse_pksj(tc)
        for slot in slots:
            print(f"  -> weeks={slot.weeks}, weekday={slot.weekday}, sections={slot.sections}")
    
    # 测试冲突检测
    print("\n\n冲突检测测试:")
    pksj1 = "7-9周 星期二[3-5节]"
    pksj2 = "8-10周 星期二[4-6节]"
    conflicts = check_courses_conflict(pksj1, pksj2)
    if conflicts:
        for c in conflicts:
            print(f"  冲突: {format_conflict_description(c)}")
    else:
        print("  无冲突")
