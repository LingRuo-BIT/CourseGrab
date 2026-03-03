# -*- coding: utf-8 -*-
"""
Pydantic 数据模型
用于 API 请求/响应的数据验证
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ==================== 课程相关模型 ====================

class CourseInfo(BaseModel):
    """课程信息"""
    wid: str = Field(alias="WID", description="唯一标识")
    kcdm: str = Field(alias="KCDM", description="课程代码")
    kcmc: str = Field(alias="KCMC", description="课程名称")
    kcmcyw: Optional[str] = Field(None, alias="KCMCYW", description="课程英文名称")
    bjdm: str = Field(alias="BJDM", description="班级代码")
    bjmc: str = Field(alias="BJMC", description="班级名称")
    rkjs: Optional[str] = Field(None, alias="RKJS", description="任课教师")
    xnxqmc: Optional[str] = Field(None, alias="XNXQMC", description="学年学期名称")
    xqmc: Optional[str] = Field(None, alias="XQMC", description="校区名称")
    kcxf: Optional[float] = Field(None, alias="KCXF", description="课程学分")
    kxrs: Optional[int] = Field(None, alias="KXRS", description="可选人数")
    dqrs: Optional[int] = Field(None, alias="DQRS", description="当前人数")
    yxxkjgrs: Optional[int] = Field(None, alias="YXXKJGRS", description="有效选课结果人数")
    pksj: Optional[str] = Field(None, alias="PKSJ", description="排课时间")
    pkdd: Optional[str] = Field(None, alias="PKDD", description="排课地点")
    pksjdd: Optional[str] = Field(None, alias="PKSJDD", description="排课时间地点")
    is_conflict: Optional[int] = Field(0, alias="IS_CONFLICT", description="是否与已选课程冲突")
    kckkdwmc: Optional[str] = Field(None, alias="KCKKDWMC", description="开课单位名称")
    kclbmc: Optional[str] = Field(None, alias="KCLBMC", description="课程类别名称")
    skfsmc: Optional[str] = Field(None, alias="SKFSMC", description="授课方式")
    
    class Config:
        populate_by_name = True


class CourseSearchRequest(BaseModel):
    """课程搜索请求"""
    keyword: str = Field(..., description="搜索关键词")
    page_index: int = Field(1, ge=1, description="页码")
    page_size: int = Field(10, ge=1, le=50, description="每页数量")


class CourseSearchResponse(BaseModel):
    """课程搜索响应"""
    courses: List[CourseInfo]
    total: int
    page_index: int
    page_size: int


# ==================== 抢课队列模型 ====================

class GrabTaskCreate(BaseModel):
    """创建抢课任务请求"""
    bjdm: str = Field(..., description="班级代码")
    kcdm: str = Field(..., description="课程代码")
    kcmc: str = Field(..., description="课程名称")
    bjmc: Optional[str] = None
    rkjs: Optional[str] = None
    pksj: Optional[str] = None
    pkdd: Optional[str] = None
    xnxqmc: Optional[str] = None
    kxrs: Optional[int] = None
    dqrs: Optional[int] = None
    priority: int = 0


class GrabTaskResponse(BaseModel):
    """抢课任务响应"""
    id: int
    bjdm: str
    kcdm: str
    kcmc: str
    bjmc: Optional[str]
    rkjs: Optional[str]
    pksj: Optional[str]
    pkdd: Optional[str]
    xnxqmc: Optional[str]
    kxrs: Optional[int]
    dqrs: Optional[int]
    priority: int
    status: str
    error_msg: Optional[str]
    created_at: datetime
    updated_at: datetime
    is_queue_conflict: bool = Field(False, description="是否与队列中其他课程冲突")
    
    class Config:
        from_attributes = True


class GrabTaskBatchAdd(BaseModel):
    """批量添加抢课任务"""
    tasks: List[GrabTaskCreate]


# ==================== 课表模型 ====================

class TimeSlot(BaseModel):
    """时间段"""
    weeks: List[int] = Field(..., description="周次列表")
    weekday: int = Field(..., ge=1, le=7, description="星期几（1-7）")
    sections: List[int] = Field(..., description="节次列表")


class ScheduleCourse(BaseModel):
    """课表中的课程"""
    bjdm: str
    kcdm: str
    kcmc: str
    bjmc: Optional[str]
    rkjs: Optional[str]
    pkdd: Optional[str]
    time_slots: List[TimeSlot]
    is_conflict: bool = False
    conflict_with: List[str] = Field(default_factory=list, description="冲突的课程bjdm列表")


class ScheduleResponse(BaseModel):
    """课表响应"""
    semester: str = Field(..., description="学期名称")
    courses: List[ScheduleCourse]
    conflicts: List[Dict[str, Any]] = Field(default_factory=list, description="冲突详情")


# ==================== 冲突检测模型 ====================

class ConflictDetail(BaseModel):
    """冲突详情"""
    course1_bjdm: str
    course1_kcmc: str
    course2_bjdm: str
    course2_kcmc: str
    conflict_weeks: List[int]
    conflict_weekday: int
    conflict_sections: List[int]
    description: str


class ConflictCheckRequest(BaseModel):
    """冲突检测请求"""
    bjdm: str = Field(..., description="要检测的课程班级代码")
    pksj: str = Field(..., description="排课时间")


class ConflictCheckResponse(BaseModel):
    """冲突检测响应"""
    has_conflict: bool
    conflicts_with_selected: List[ConflictDetail] = Field(default_factory=list)
    conflicts_with_queue: List[ConflictDetail] = Field(default_factory=list)


# ==================== 通知配置模型 ====================

class NotificationConfigUpdate(BaseModel):
    """通知配置更新"""
    email_enabled: bool = False
    email_smtp_host: Optional[str] = None
    email_smtp_port: Optional[int] = None
    email_username: Optional[str] = None
    email_password: Optional[str] = None
    email_to: Optional[str] = None
    wecom_enabled: bool = False
    wecom_webhook: Optional[str] = None


class NotificationConfigResponse(BaseModel):
    """通知配置响应"""
    email_enabled: bool
    email_smtp_host: Optional[str]
    email_smtp_port: Optional[int]
    email_username: Optional[str]
    email_to: Optional[str]
    wecom_enabled: bool
    wecom_webhook: Optional[str]
    
    class Config:
        from_attributes = True


# ==================== 认证模型 ====================

class CredentialStatus(BaseModel):
    """凭证状态"""
    is_valid: bool
    has_cookies: bool
    has_csrf_token: bool
    updated_at: Optional[datetime]


class ProxyStatus(BaseModel):
    """代理状态"""
    is_running: bool
    host: str
    port: int


# ==================== 抢课引擎模型 ====================

class GrabberStatus(BaseModel):
    """抢课引擎状态"""
    is_running: bool
    active_tasks: int
    success_count: int
    failed_count: int
    current_tasks: List[Dict[str, Any]]


class GrabStartRequest(BaseModel):
    """开始抢课请求"""
    task_ids: Optional[List[int]] = Field(None, description="指定任务ID列表，为空则抢所有pending任务")


class GrabStopRequest(BaseModel):
    """停止抢课请求"""
    task_ids: Optional[List[int]] = Field(None, description="指定任务ID列表，为空则停止所有")


# ==================== 通用响应模型 ====================

class ApiResponse(BaseModel):
    """通用 API 响应"""
    success: bool
    message: str
    data: Optional[Any] = None
