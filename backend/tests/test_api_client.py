# -*- coding: utf-8 -*-
"""
api_client.py 测试脚本
用于测试 BitApiClient 的各项功能
"""

import asyncio
import json
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import AsyncSessionLocal, init_db
from services.api_client import BitApiClient


async def test_connection():
    """测试基本连接"""
    print("=" * 50)
    print("测试 1: 基本连接测试")
    print("=" * 50)
    
    async with AsyncSessionLocal() as db:
        client = BitApiClient(db)
        
        # 测试加载凭证
        has_cookies = await client._ensure_cookies()
        print(f"凭证状态: {'已加载' if has_cookies else '未配置'}")
        
        if has_cookies:
            print(f"Cookies 数量: {len(client._cookies)}")
            print(f"CSRF Token: {client._csrf_token[:20] if client._csrf_token else '无'}...")
        
        return has_cookies


async def test_check_cookies_valid():
    """测试 Cookie 有效性检查"""
    print("\n" + "=" * 50)
    print("测试 2: Cookie 有效性检查")
    print("=" * 50)
    
    async with AsyncSessionLocal() as db:
        client = BitApiClient(db)
        
        is_valid = await client.check_cookies_valid()
        print(f"Cookie 有效: {is_valid}")
        
        return is_valid


async def test_fetch_csrf_token():
    """测试获取 CSRF Token"""
    print("\n" + "=" * 50)
    print("测试 3: 获取 CSRF Token")
    print("=" * 50)
    
    async with AsyncSessionLocal() as db:
        client = BitApiClient(db)
        
        token = await client.fetch_csrf_token()
        
        if token:
            print(f"获取成功: {token[:30]}...")
        else:
            print("获取失败 - Cookie 可能已过期")
        
        return bool(token)


async def test_search_courses(keyword: str = "数学"):
    """测试课程搜索"""
    print("\n" + "=" * 50)
    print(f"测试 4: 搜索课程 (关键词: {keyword})")
    print("=" * 50)
    
    async with AsyncSessionLocal() as db:
        client = BitApiClient(db)
        
        result = await client.search_courses(keyword, page_index=1, page_size=5)
        
        courses = result.get("datas", [])
        total = result.get("total", 0)
        
        print(f"搜索结果: 共 {total} 门课程, 返回 {len(courses)} 条")
        
        for i, course in enumerate(courses[:3], 1):
            print(f"  {i}. {course.get('KCMC', 'N/A')} - {course.get('RKJS', 'N/A')}")
            print(f"     班级: {course.get('BJMC', 'N/A')}, 人数: {course.get('DQRS', 0)}/{course.get('KXRS', 0)}")
        
        return len(courses) > 0


async def test_get_selected_courses():
    """测试获取已选课程"""
    print("\n" + "=" * 50)
    print("测试 5: 获取已选课程")
    print("=" * 50)
    
    async with AsyncSessionLocal() as db:
        client = BitApiClient(db)
        
        courses = await client.get_selected_courses()
        
        print(f"已选课程数量: {len(courses)}")
        
        for i, course in enumerate(courses[:5], 1):
            print(f"  {i}. {course.get('KCMC', 'N/A')} - {course.get('BJMC', 'N/A')}")
            print(f"     时间: {course.get('PKSJDD', course.get('PKSJ', 'N/A'))}")
        
        return True


async def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("  BitApiClient 功能测试")
    print("=" * 60)
    
    # 初始化数据库
    await init_db()
    
    results = {}
    
    # 测试 1: 基本连接
    results["连接测试"] = await test_connection()
    
    if not results["连接测试"]:
        print("\n[!] 未配置凭证，无法继续其他测试")
        print("    请先在 Web 界面配置 Cookie")
        return results
    
    # 测试 2: Cookie 有效性
    results["Cookie有效性"] = await test_check_cookies_valid()
    
    if not results["Cookie有效性"]:
        print("\n[!] Cookie 已失效，部分测试可能失败")
    
    # 测试 3: 获取 CSRF Token
    results["CSRF_Token"] = await test_fetch_csrf_token()
    
    # 测试 4: 搜索课程
    results["搜索课程"] = await test_search_courses()
    
    # 测试 5: 获取已选课程
    results["已选课程"] = await test_get_selected_courses()
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("  测试结果汇总")
    print("=" * 60)
    
    for name, passed in results.items():
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"  {name}: {status}")
    
    passed_count = sum(1 for v in results.values() if v)
    total_count = len(results)
    print(f"\n  总计: {passed_count}/{total_count} 通过")
    
    return results


if __name__ == "__main__":
    print("启动 api_client 测试...")
    
    # 如果有命令行参数，作为搜索关键词
    if len(sys.argv) > 1:
        keyword = sys.argv[1]
        asyncio.run(test_search_courses(keyword))
    else:
        asyncio.run(run_all_tests())
