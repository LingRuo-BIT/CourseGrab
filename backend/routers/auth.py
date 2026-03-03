# -*- coding: utf-8 -*-
"""
认证相关路由（Cookie代理抓包）
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json
from datetime import datetime

from database import get_db, Credential
from models import ApiResponse, CredentialStatus
from services.api_client import BitApiClient

router = APIRouter(prefix="/auth", tags=["认证"])


@router.get("/status", response_model=ApiResponse)
async def get_credential_status(
    db: AsyncSession = Depends(get_db),
    verify: bool = False,  # 是否进行实际验证
):
    """
    获取凭证状态
    verify=True 时会实际调用API验证Cookie是否过期，并返回用户信息
    """
    result = await db.execute(
        select(Credential)
        .where(Credential.is_valid == True)
        .order_by(Credential.updated_at.desc())
        .limit(1)
    )
    credential = result.scalar_one_or_none()
    
    if credential:
        has_cookies = bool(credential.cookies)
        has_csrf_token = bool(credential.csrf_token)
        is_valid = credential.is_valid
        student_info = None
        
        # 如果请求验证，进行实际API调用检查并获取用户信息
        if verify and has_cookies:
            client = BitApiClient(db)
            student_info = await client.get_student_info()
            is_valid = student_info is not None
            
            # 更新数据库中的有效性状态
            if is_valid != credential.is_valid:
                credential.is_valid = is_valid
                await db.commit()
        
        if is_valid:
            message = "凭证有效"
        elif has_cookies:
            message = "凭证已失效"
        else:
            message = "凭证无效"
        
        return ApiResponse(
            success=True,
            message=message,
            data={
                "is_valid": is_valid,
                "has_cookies": has_cookies,
                "has_csrf_token": has_csrf_token,
                "updated_at": credential.updated_at.isoformat() if credential.updated_at else None,
                # 用户信息
                "student_name": student_info.get("XM") if student_info else None,
                "student_id": student_info.get("XH") if student_info else None,
                "college": student_info.get("YXMC") if student_info else None,
                "major": student_info.get("ZYMC") if student_info else None,
            }
        )
    else:
        return ApiResponse(
            success=True,
            message="未配置凭证",
            data={
                "is_valid": False,
                "has_cookies": False,
                "has_csrf_token": False,
                "updated_at": None,
                "student_name": None,
                "student_id": None,
                "college": None,
                "major": None,
            }
        )


@router.post("/cookies", response_model=ApiResponse)
async def update_cookies(
    cookies: dict,
    db: AsyncSession = Depends(get_db),
):
    """
    手动更新 Cookie，先验证有效性再保存
    """
    # 先验证新 Cookie 是否有效
    client = BitApiClient(db)
    await client.refresh_cookies(cookies)
    student_info = await client.get_student_info()
    is_valid = student_info is not None
    
    # 验证失败，不保存新 Cookie
    if not is_valid:
        return ApiResponse(
            success=False,
            message="Cookie 无效或已过期，请重新获取",
            data={
                "is_valid": False,
                "has_csrf_token": False,
            }
        )
    
    # Cookie 有效，保存到数据库
    result = await db.execute(select(Credential).limit(1))
    credential = result.scalar_one_or_none()
    
    if credential:
        credential.cookies = json.dumps(cookies)
        credential.is_valid = True
        credential.csrf_token = None
        credential.updated_at = datetime.now()
    else:
        credential = Credential(
            cookies=json.dumps(cookies),
            is_valid=True,
        )
        db.add(credential)
    
    await db.commit()
    
    # 尝试获取 csrf_token
    token = await client.fetch_csrf_token()
    
    return ApiResponse(
        success=True,
        message="Cookie 保存成功" + (f"，CSRF Token 已获取" if token else ""),
        data={
            "is_valid": True,
            "has_csrf_token": bool(token),
            "student_name": student_info.get("XM"),
            "student_id": student_info.get("XH"),
        }
    )


@router.get("/system-info", response_model=ApiResponse)
async def get_system_info(
    db: AsyncSession = Depends(get_db),
):
    """
    获取选课系统信息（选课阶段、时间等）
    """
    client = BitApiClient(db)
    info = await client.get_system_info()
    
    if not info:
        return ApiResponse(
            success=False,
            message="获取系统信息失败，可能 Cookie 已过期",
        )
    
    # 提取选课阶段信息
    lcxx = info.get("lcxx") or {}
    
    return ApiResponse(
        success=True,
        message="获取成功",
        data={
            "current_time": info.get("dqsj"),
            "is_open": info.get("xksfkf") == 1,
            # 选课阶段信息
            "phase_name": lcxx.get("MC"),
            "phase_start": lcxx.get("KFKSSJ"),
            "phase_end": lcxx.get("KFJSSJ"),
            "semester": lcxx.get("XNXQDM"),
        }
    )


@router.post("/refresh-token", response_model=ApiResponse)
async def refresh_csrf_token(
    db: AsyncSession = Depends(get_db),
):
    """
    刷新 CSRF Token
    """
    client = BitApiClient(db)
    token = await client.fetch_csrf_token()
    
    if token:
        return ApiResponse(
            success=True,
            message="Token 刷新成功",
            data={"csrf_token": token[:20] + "..."},
        )
    else:
        return ApiResponse(
            success=False,
            message="Token 刷新失败，可能 Cookie 已过期",
        )


@router.post("/validate", response_model=ApiResponse)
async def validate_cookies(
    db: AsyncSession = Depends(get_db),
):
    """
    验证 Cookie 是否有效
    """
    client = BitApiClient(db)
    is_valid = await client.check_cookies_valid()
    
    return ApiResponse(
        success=is_valid,
        message="Cookie 有效" if is_valid else "Cookie 无效或已过期",
    )


@router.delete("/cookies", response_model=ApiResponse)
async def clear_cookies(
    db: AsyncSession = Depends(get_db),
):
    """
    清除 Cookie
    """
    result = await db.execute(select(Credential))
    credentials = result.scalars().all()
    
    for c in credentials:
        c.is_valid = False
        c.cookies = None
        c.csrf_token = None
    
    await db.commit()
    
    return ApiResponse(
        success=True,
        message="Cookie 已清除",
    )
