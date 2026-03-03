# -*- coding: utf-8 -*-
"""
选课系统 API 客户端
封装与 xk.bit.edu.cn 的所有 HTTP 交互
"""

import time
import json
import asyncio
from typing import Optional, Dict, List, Any
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from config import settings
from database import Credential


class BitApiClient:
    """BIT 选课系统 API 客户端"""
    
    # API 端点
    ENDPOINTS = {
        "public_info": "/xsxkHome/loadPublicInfo_course.do",
        "load_std_info": "/xsxkHome/loadStdInfo.do",
        "load_public_info_index": "/xsxkHome/loadPublicInfo_index.do",
        "load_dw_xb": "/xsxkHome/loadDwXb.do",
        "search_course": "/xsxkCourse/loadAllCourseInfo.do",
        "selected_courses": "/xsxkCourse/loadStdCourseInfo.do",
        "choose_course": "/xsxkCourse/choiceCourse.do",
        "cancel_course": "/xsxkCourse/cancelCourse.do",
    }
    
    # 默认请求头
    DEFAULT_HEADERS = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Pragma": "no-cache",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "sec-ch-ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.base_url = settings.api_base_url
        self.timeout = settings.request_timeout
        self._cookies: Optional[Dict[str, str]] = None
        self._csrf_token: Optional[str] = None
    
    async def _get_credential(self) -> Optional[Credential]:
        """从数据库获取有效凭证"""
        result = await self.db.execute(
            select(Credential)
            .where(Credential.is_valid == True)
            .order_by(Credential.updated_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
    
    async def _load_cookies(self) -> bool:
        """加载 Cookie"""
        credential = await self._get_credential()
        if credential and credential.cookies:
            try:
                self._cookies = json.loads(credential.cookies)
                self._csrf_token = credential.csrf_token
                return True
            except json.JSONDecodeError:
                pass
        return False
    
    async def _ensure_cookies(self) -> bool:
        """确保 Cookie 已加载"""
        if not self._cookies:
            return await self._load_cookies()
        return True
    
    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        headers = self.DEFAULT_HEADERS.copy()
        headers["Origin"] = settings.bit_base_url
        headers["Referer"] = f"{settings.bit_base_url}/yjsxkapp/sys/xsxkappbit/course.html"
        return headers
    
    def _get_timestamp(self) -> str:
        """获取时间戳参数"""
        return str(int(time.time() * 1000))
    
    async def fetch_csrf_token(self) -> Optional[str]:
        """获取 CSRF Token"""
        if not await self._ensure_cookies():
            return None
        
        url = f"{self.base_url}{self.ENDPOINTS['public_info']}"
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(
                    url,
                    headers=self._get_headers(),
                    cookies=self._cookies,
                    params={"_": self._get_timestamp()}
                )
                data = response.json()
                
                if "csrfToken" in data:
                    self._csrf_token = data["csrfToken"]
                    
                    # 更新数据库中的 csrf_token
                    credential = await self._get_credential()
                    if credential:
                        credential.csrf_token = self._csrf_token
                        await self.db.commit()

                    print(f"获取 csrfToken 成功:{self._csrf_token[:20]}...")

                    return self._csrf_token
            except Exception as e:
                print(f"获取 csrfToken 失败: {e}")
        
        return None
    
    async def search_courses(
        self,
        keyword: str,
        page_index: int = 1,
        page_size: int = 10,
        college: str = "",
        conflict_only: str = "",
        full_only: str = "",
    ) -> Dict[str, Any]:
        """
        搜索课程
        
        Args:
            keyword: 搜索关键词
            page_index: 页码
            page_size: 每页数量
            college: 开课学院代码
            conflict_only: 是否只显示冲突课程
            full_only: 是否只显示已满课程
        
        Returns:
            包含 datas, pageIndex, pageSize, total 的字典
        """
        if not await self._ensure_cookies():
            return {"datas": [], "total": 0, "pageIndex": page_index, "pageSize": page_size}
        
        url = f"{self.base_url}{self.ENDPOINTS['search_course']}"
        
        data = {
            "query_keyword": keyword,
            "query_kkyx": college,
            "query_sfct": conflict_only,
            "query_sfym": full_only,
            "fixedAutoSubmitBug": "",
            "pageIndex": str(page_index),
            "pageSize": str(page_size),
            "sortField": "",
            "sortOrder": "",
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    url,
                    headers=self._get_headers(),
                    cookies=self._cookies,
                    data=data,
                    params={"_": self._get_timestamp()}
                )
                result = response.json()
                return result
            except Exception as e:
                print(f"搜索课程失败: {e}")
                return {"datas": [], "total": 0, "pageIndex": page_index, "pageSize": page_size}
    
    async def get_selected_courses(self) -> List[Dict[str, Any]]:
        """获取已选课程列表"""
        if not await self._ensure_cookies():
            return []
        
        url = f"{self.base_url}{self.ENDPOINTS['selected_courses']}"
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(
                    url,
                    headers=self._get_headers(),
                    cookies=self._cookies,
                    params={"_": self._get_timestamp()}
                )
                result = response.json()
                
                # 返回格式可能是 {"results": [...]} 或 {"datas": [...]} 或直接是列表
                if isinstance(result, dict):
                    if "results" in result:
                        return result["results"]
                    elif "datas" in result:
                        return result["datas"]
                elif isinstance(result, list):
                    return result

                return []
            except Exception as e:
                print(f"获取已选课程失败: {e}")
                return []
    
    async def choose_course(self, bjdm: str, retry: bool = True) -> Dict[str, Any]:
        """
        选课/抢课
        
        Args:
            bjdm: 班级代码
            retry: 是否在 token 过期时自动重试
        
        Returns:
            选课结果，包含 code 和 msg
        """
        if not await self._ensure_cookies():
            return {"code": -1, "msg": "未登录或 Cookie 失效"}
        
        # 确保有 csrf_token
        if not self._csrf_token:
            await self.fetch_csrf_token()
        
        if not self._csrf_token:
            return {"code": -1, "msg": "获取 csrfToken 失败"}
        
        url = f"{self.base_url}{self.ENDPOINTS['choose_course']}"
        
        data = {
            "bjdm": bjdm,
            "lx": "1",
            "csrfToken": self._csrf_token
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    url,
                    headers=self._get_headers(),
                    cookies=self._cookies,
                    data=data,
                    params={"_": self._get_timestamp()}
                )
                result = response.json()
                
                # 检查是否 token 过期，自动刷新重试
                if result.get("code") == 0 and "页面已过期" in result.get("msg", ""):
                    if retry:
                        print("选课 csrfToken 过期，正在刷新重试...")
                        await self.fetch_csrf_token()
                        return await self.choose_course(bjdm, retry=False)
                    result["token_expired"] = True
                
                return result
            except Exception as e:
                return {"code": -1, "msg": f"请求失败: {e}"}
    
    async def cancel_course(self, bjdm: str, retry: bool = True) -> Dict[str, Any]:
        """
        退课
        
        Args:
            bjdm: 班级代码
            retry: 是否在 token 过期时自动重试
        
        Returns:
            退课结果，包含 code 和 msg
        """
        if not await self._ensure_cookies():
            return {"code": -1, "msg": "未登录或 Cookie 失效"}
        
        # 确保有 csrf_token
        if not self._csrf_token:
            await self.fetch_csrf_token()
        
        if not self._csrf_token:
            return {"code": -1, "msg": "获取 csrfToken 失败"}
        
        url = f"{self.base_url}{self.ENDPOINTS['cancel_course']}"
        
        data = {
            "bjdm": bjdm,
            "csrfToken": self._csrf_token
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    url,
                    headers=self._get_headers(),
                    cookies=self._cookies,
                    data=data,
                    params={"_": self._get_timestamp()}
                )
                result = response.json()
                
                # 检查是否 token 过期，自动刷新重试
                if result.get("code") == 0 and "页面已过期" in result.get("msg", ""):
                    if retry:
                        print("退课 csrfToken 过期，正在刷新重试...")
                        await self.fetch_csrf_token()
                        return await self.cancel_course(bjdm, retry=False)
                    result["token_expired"] = True
                
                return result
            except Exception as e:
                return {"code": -1, "msg": f"请求失败: {e}"}
    
    async def refresh_cookies(self, cookies: Dict[str, str]) -> bool:
        """刷新 Cookie"""
        self._cookies = cookies
        self._csrf_token = None
        
        # 保存到数据库
        credential = await self._get_credential()
        if credential:
            credential.cookies = json.dumps(cookies)
            credential.csrf_token = None
            credential.is_valid = True
        else:
            credential = Credential(
                cookies=json.dumps(cookies),
                is_valid=True
            )
            self.db.add(credential)
        
        await self.db.commit()
        
        # 获取新的 csrf_token
        await self.fetch_csrf_token()
        
        return True
    
    async def get_student_info(self) -> Optional[Dict[str, Any]]:
        """
        获取学生信息
        用于验证Cookie有效性和获取用户基本信息
        
        Returns:
            成功时返回学生信息字典，失败返回 None
        """
        if not await self._ensure_cookies():
            return None
        
        url = f"{self.base_url}{self.ENDPOINTS['load_std_info']}"
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(
                    url,
                    headers=self._get_headers(),
                    cookies=self._cookies,
                    params={"_": self._get_timestamp()}
                )
                
                # 401 表示 Cookie 无效
                if response.status_code == 401:
                    return None
                
                result = response.json()
                
                # code == '1' 表示成功
                if result.get("code") == "1" and result.get("xs"):
                    return result["xs"]
                
                return None
            except Exception as e:
                print(f"获取学生信息失败: {e}")
                return None
    
    async def get_system_info(self) -> Optional[Dict[str, Any]]:
        """
        获取选课系统信息
        包含选课阶段、时间等信息
        
        Returns:
            成功时返回系统信息字典，失败返回 None
        """
        if not await self._ensure_cookies():
            return None
        
        url = f"{self.base_url}{self.ENDPOINTS['load_public_info_index']}"
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(
                    url,
                    headers=self._get_headers(),
                    cookies=self._cookies,
                )
                
                if response.status_code == 401:
                    return None
                
                return response.json()
            except Exception as e:
                print(f"获取选课系统信息失败: {e}")
                return None
    
    async def get_departments(self) -> List[Dict[str, str]]:
        """
        获取开课院系列表
        
        Returns:
            院系列表，每个元素包含 code (DM) 和 name (MC)
        """
        if not await self._ensure_cookies():
            return []
        
        url = f"{self.base_url}{self.ENDPOINTS['load_dw_xb']}"
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(
                    url,
                    headers=self._get_headers(),
                    cookies=self._cookies,
                    params={"_": self._get_timestamp()}
                )
                
                result = response.json()
                
                # dwxb 是 JSON 字符串，需要二次解析
                if "dwxb" in result:
                    dw_list = json.loads(result["dwxb"])
                    return [
                        {"code": item.get("DM", ""), "name": item.get("MC", "")}
                        for item in dw_list
                    ]
                
                return []
            except Exception as e:
                print(f"获取院系列表失败: {e}")
                return []
    
    async def check_cookies_valid(self) -> bool:
        """检查 Cookie 是否有效（使用学生信息接口验证）"""
        student_info = await self.get_student_info()
        return student_info is not None


# 创建全局客户端实例的工厂函数
async def get_api_client(db: AsyncSession) -> BitApiClient:
    """获取 API 客户端实例"""
    return BitApiClient(db)

